"""Announcement email from the ops server, and the domain's DMARC record.

In plain words: an operator writes an email on the ops pages and the ops server
sends it through SES (Amazon Simple Email Service). This construct gives the ops
server what it needs for that, and nothing more.

Three switches in the ``email`` block of ``pa_config.json``:

* ``enabled`` (the SES sender that Cognito already uses) adds the **DMARC
  record**: a DNS entry, ``_dmarc.<sender domain>``, that tells other mail
  servers what to do with email that falsely claims to come from the domain.
  ``p=none`` only asks them to report; it blocks nothing.
* ``pictures`` adds **picture hosting**: a private S3 bucket (Amazon Simple
  Storage Service) that the site's existing CloudFront distribution (the
  content delivery network in front of the site) serves at
  ``/email-images/*``. Origin access control means only that distribution may
  read the bucket. Leave it on once an email with a picture has gone out: the
  pictures in sent emails are served from here. The bucket is kept even if the
  switch goes off or the stack is deleted.
* ``announcements`` adds **sending**: permission for the ops task role to send
  only from ``updates@<sender domain>`` and to read the SES suppression list
  (the addresses that bounced or marked our email as spam; SES does not let
  that permission be limited to one sender, so its resource is ``*``), and the
  ops settings (From and reply addresses, the public site and API addresses).
  Without them the ops server answers 503 on the send routes. To stop sending,
  turn this switch off and leave ``pictures`` on.

With both ``pictures`` and ``announcements`` on, the ops server may also add
pictures to the bucket (never read, list or delete them) and is told the
bucket's name. With ``pictures`` off, sending still works and the picture
upload answers 503.
"""

from aws_cdk import (
    RemovalPolicy,
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as cloudfront_origins,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_route53 as r53,
    aws_s3 as s3,
)
from constructs import Construct

IMAGE_PATH_PATTERN = "/email-images/*"
IMAGE_KEY_PREFIX = "email-images/"
DMARC_VALUE = "v=DMARC1; p=none"


class Email(Construct):
    """The DMARC record, picture hosting and announcement sending, each behind its switch.

    Args:
        scope: The parent construct, normally the application stack.
        id: The construct id.
        email_config: The ``email`` block of ``pa_config.json``, or None (no email).
        hosted_zone: The zone that holds the sender domain.
        distribution: The public site's CloudFront distribution.
        response_headers_policy: The site's security headers policy, reused for pictures.
        ops_task_role: The ops server's task role.
        ops_container: The ops server's container.
        public_site_url: The public site's address, for example ``https://example.org``.
        public_api_url: The public API's address, for example ``https://api.example.org``.

    Raises:
        ValueError: The sender domain is not inside the hosted zone's domain.

    Attributes:
        image_bucket: The picture bucket, or None when pictures are off.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        email_config: dict | None,
        hosted_zone: r53.IHostedZone,
        distribution: cloudfront.Distribution,
        response_headers_policy: cloudfront.IResponseHeadersPolicy,
        ops_task_role: iam.IRole,
        ops_container: ecs.ContainerDefinition,
        public_site_url: str,
        public_api_url: str,
    ) -> None:
        super().__init__(scope, id)
        self.image_bucket = None
        email_config = email_config or {}
        sender_domain = email_config.get("sender_domain")

        if email_config.get("enabled"):
            zone_name = hosted_zone.zone_name.rstrip(".")
            if sender_domain != zone_name and not sender_domain.endswith(f".{zone_name}"):
                raise ValueError(
                    f"email.sender_domain {sender_domain!r} is not inside the hosted zone {zone_name!r}."
                )
            r53.TxtRecord(self, "DmarcRecord",
                zone=hosted_zone,
                record_name=f"_dmarc.{sender_domain}",
                values=[DMARC_VALUE],
            )

        if email_config.get("pictures"):
            self.image_bucket = s3.Bucket(self, "ImageBucket",
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
                enforce_ssl=True,
                versioned=False,
                removal_policy=RemovalPolicy.RETAIN,
            )
            # The key is the path (email-images/<name>), so no rewrite is needed.
            distribution.add_behavior(
                IMAGE_PATH_PATTERN,
                cloudfront_origins.S3BucketOrigin.with_origin_access_control(self.image_bucket),
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=response_headers_policy,
            )

        if not email_config.get("announcements"):
            return

        from_address = f"updates@{sender_domain}"
        ops_task_role.add_to_principal_policy(iam.PolicyStatement(
            actions=["ses:SendEmail"],
            resources=[Stack.of(self).format_arn(
                service="ses", resource="identity", resource_name=sender_domain,
            )],
            conditions={"StringEquals": {"ses:FromAddress": from_address}},
        ))
        ops_task_role.add_to_principal_policy(iam.PolicyStatement(
            actions=["ses:ListSuppressedDestinations"],
            resources=["*"],
        ))
        settings = {
            "ANNOUNCEMENT_FROM_ADDRESS": f"{email_config['from_name']} <{from_address}>",
            "ANNOUNCEMENT_REPLY_TO": email_config["reply_to"],
            "PUBLIC_SITE_URL": public_site_url,
            "PUBLIC_API_URL": public_api_url,
        }
        if self.image_bucket:
            # Add only: no read, list or delete, so a sent picture is never changed.
            ops_task_role.add_to_principal_policy(iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[self.image_bucket.arn_for_objects(f"{IMAGE_KEY_PREFIX}*")],
            ))
            settings["ANNOUNCEMENT_IMAGE_BUCKET"] = self.image_bucket.bucket_name
        for name, value in settings.items():
            ops_container.add_environment(name, value)
