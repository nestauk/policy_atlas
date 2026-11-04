"""The queued document-ingest worker (task 057): a queue, its dead-letter queue and a function.

In plain words: when a run needs the full text of documents, the API puts one
message per document on a queue, and AWS starts a copy of the ingest function
for each message. The function downloads the document, reads (parses) it and
writes the passages to the database. It does no AI calls.

The pieces, one line each:

* **SQS queue** (Amazon Simple Queue Service): a managed to-do list of messages.
  A message that is taken but not finished reappears for another try.
* **Visibility timeout**: how long a taken message stays hidden from other
  workers. If the function has not finished by then, the message reappears.
  It is the function timeout plus 30 seconds, so a message never reappears
  while its first try is still running.
* **Dead-letter queue**: a second queue where a message lands after its second
  failed try, so it stops being retried and a person can look at it.
* **Event-source mapping**: the AWS-managed poller that reads the queue and
  starts the function, one message per start, at most ``MAX_CONCURRENCY``
  copies at a time.
* **Lambda function**: the backend container image, started with a different
  command (the handler below) instead of the web server.

The function reads its database password at start-up from Secrets Manager
(through its own permission, never through an environment variable) and holds
no AI model key and no Bedrock permission: embedding stays in the API's run
(contract D6).
"""

from aws_cdk import (
    Duration,
    Size,
    aws_cloudwatch as cloudwatch,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_sqs as sqs,
)
from constructs import Construct

# Contract N4 / D4 / D5 / N5. The infra tests pin each of these.
FUNCTION_TIMEOUT = Duration.seconds(180)
FUNCTION_MEMORY_MB = 1769  # one full CPU core in Lambda (D5)
FUNCTION_EPHEMERAL_STORAGE_MB = 512
# Function timeout + 30 s: a redelivered message lands inside the 600 s stage
# deadline, and never while the first try is still running (finding 7).
QUEUE_VISIBILITY_TIMEOUT = Duration.seconds(180 + 30)
QUEUE_RETENTION = Duration.days(4)
DEAD_LETTER_RETENTION = Duration.days(14)
MAX_RECEIVE_COUNT = 2  # the second failed try moves the message to the dead-letter queue
MAX_CONCURRENCY = 20  # raised only on a staging measurement (N5)
HANDLER_COMMAND = ["python", "-m", "awslambdaric", "policy_atlas.ops.ingest_worker.handler"]

QUEUE_NAME = "policy-atlas-v3-ingest"
DEAD_LETTER_QUEUE_NAME = "policy-atlas-v3-ingest-dlq"
FUNCTION_NAME = "policy-atlas-v3-ingest"
LOG_GROUP_NAME = "/policy_atlas_v3/ingest"
DEAD_LETTER_ALARM_NAME = "policy-atlas-v3-ingest-dlq-depth"


class IngestWorker(Construct):
    """Queue, dead-letter queue, ingest function and the dead-letter alarm.

    Attributes:
        queue: The ingest queue the API sends one message per document to.
        dead_letter_queue: Where a message lands after its second failed try.
        function: The ingest Lambda function.
        security_group: The function's security group (outbound only: 80 and
            443 to the internet and 5432 to the database group, which admits it).
        dead_letter_alarm: Fires when any message sits in the dead-letter queue.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: ec2.IVpc,
        image_asset: ecr_assets.DockerImageAsset,
        db_secret: secretsmanager.ISecret,
        db_security_group: ec2.ISecurityGroup,
        model_route: str,
    ) -> None:
        super().__init__(scope, id)

        self.dead_letter_queue = sqs.Queue(
            self,
            "DeadLetterQueue",
            queue_name=DEAD_LETTER_QUEUE_NAME,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            retention_period=DEAD_LETTER_RETENTION,
        )
        self.queue = sqs.Queue(
            self,
            "Queue",
            queue_name=QUEUE_NAME,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            retention_period=QUEUE_RETENTION,
            visibility_timeout=QUEUE_VISIBILITY_TIMEOUT,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=MAX_RECEIVE_COUNT,
                queue=self.dead_letter_queue,
            ),
        )

        # Outbound only, and only three rules (owner ruling 2026-11-04, task 057
        # review): 80 and 443 to the internet (publishers through the NAT; SQS and
        # Secrets Manager likewise, on 443) and 5432 to the database group. A
        # publisher on another port is refused. DNS to the VPC resolver is not
        # filtered by security groups. Nothing connects in.
        self.security_group = ec2.SecurityGroup(
            self,
            "SecurityGroup",
            vpc=vpc,
            description="Policy Atlas ingest function",
            allow_all_outbound=False,
        )
        for port in (80, 443):
            self.security_group.add_egress_rule(
                peer=ec2.Peer.any_ipv4(),
                connection=ec2.Port.tcp(port),
                description=f"Allow the Policy Atlas ingest function to fetch on {port}",
            )
        # Both halves are needed when outbound is deny-by-default.
        self.security_group.add_egress_rule(
            peer=db_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow the Policy Atlas ingest function to connect to RDS",
        )
        db_security_group.add_ingress_rule(
            self.security_group,
            ec2.Port.tcp(5432),
            "Allow the Policy Atlas ingest function to connect to RDS",
        )

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=LOG_GROUP_NAME,
            retention=logs.RetentionDays.ONE_MONTH,
        )

        # Same image asset as the API and migration tasks (one build, one push);
        # only the start command differs.
        self.function = lambda_.DockerImageFunction(
            self,
            "Function",
            function_name=FUNCTION_NAME,
            code=lambda_.DockerImageCode.from_ecr(
                image_asset.repository,
                tag_or_digest=image_asset.image_tag,
                cmd=HANDLER_COMMAND,
            ),
            architecture=lambda_.Architecture.X86_64,  # the asset is built for linux/amd64
            memory_size=FUNCTION_MEMORY_MB,
            timeout=FUNCTION_TIMEOUT,
            ephemeral_storage_size=Size.mebibytes(FUNCTION_EPHEMERAL_STORAGE_MB),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.security_group],
            log_group=log_group,
            environment={
                # The ARN only: the function fetches the secret at cold start.
                "POLICY_ATLAS_DB_SECRET_ARN": db_secret.secret_arn,
                "POLICY_ATLAS_MODEL_ROUTE": model_route,
                "LOG_FORMAT": "json",
            },
        )
        db_secret.grant_read(self.function)

        self.function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.queue,
                batch_size=1,
                max_batching_window=Duration.seconds(0),
                max_concurrency=MAX_CONCURRENCY,
                report_batch_item_failures=True,
            )
        )

        # No action: the stacks have no alarm topic yet; the alarm shows its
        # state in the CloudWatch console.
        self.dead_letter_alarm = cloudwatch.Alarm(
            self,
            "DeadLetterAlarm",
            alarm_name=DEAD_LETTER_ALARM_NAME,
            alarm_description=(
                "A document message failed twice and sits in the ingest dead-letter "
                "queue. Drain and inspect it: infra/DEPLOYMENT.md, ingest function."
            ),
            metric=self.dead_letter_queue.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(5),
                statistic="Maximum",
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            # An idle queue stops reporting; no data means nothing dead-lettered.
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
