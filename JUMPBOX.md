# RDS jumpbox

The RDS jumpbox provides temporary, IAM-controlled access to a database in a
private VPC. It does not expose SSH or database ports to the internet.

Remote mode is recommended for most users. It forwards a port on your computer
to the database, allowing you to use locally installed tools such as `psql`,
DBeaver, DataGrip, or pgAdmin. Local mode instead installs PostgreSQL client
tools on the jumpbox itself.

## Prerequisites

You need:

- the AWS CLI configured for the correct account and region;
- the [AWS Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html);
- permission to start an SSM session on the jumpbox;
- permission to read the database secret; and
- a local database client when using remote mode.

Check that the Session Manager plugin is installed:

```bash
session-manager-plugin
```

Your administrator must grant the relevant `ssm:StartSession`,
`secretsmanager:GetSecretValue`, and resource-discovery permissions.

## Remote mode: connect from your computer

### 1. Retrieve the database credentials

For Policy Atlas, retrieve the generated database secret name:

```bash
DB_SECRET=$(aws ssm get-parameter \
  --name /policy_atlas_v3/db/secret_name \
  --query Parameter.Value \
  --output text)
```

Inspect the secret:

```bash
aws secretsmanager get-secret-value \
  --secret-id "$DB_SECRET" \
  --query SecretString \
  --output text | python3 -m json.tool
```

The secret contains the database hostname, port, database name, username, and
password. Treat this output as sensitive: do not paste it into tickets, logs,
or chat messages.

### 2. Start the tunnel

Copy the `PortForwardingCommand` from the `PaV3DatabaseStack` CloudFormation
outputs and run it in a terminal. You can retrieve it with:

```bash
aws cloudformation describe-stacks \
  --stack-name PaV3DatabaseStack \
  --query "Stacks[0].Outputs[?contains(OutputKey, 'PortForwardingCommand')].OutputValue | [0]" \
  --output text
```

The output will resemble:

```bash
aws ssm start-session \
  --target <jumpbox-instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host="<database-endpoint>",portNumber="5432",localPortNumber="15432"
```

Keep this terminal open for as long as you need the database connection.

### 3. Connect your database client

In another terminal, connect with `psql`:

```bash
psql "host=localhost port=15432 dbname=<database-name> user=<database-user> sslmode=require"
```

Enter the database password when prompted. For graphical clients, use:

| Setting | Value |
| --- | --- |
| Host | `localhost` |
| Port | `15432` |
| Database | Value from the database secret |
| Username | Value from the database secret |
| Password | Value from the database secret |
| SSL mode | `require` |

Although the client connects to `localhost`, traffic is forwarded through SSM
to the private database endpoint.

### 4. Close the tunnel

Exit the database client, then press `Ctrl+C` in the terminal running the SSM
session. Do not leave unused sessions running.

## Local mode: work on the jumpbox

Local mode installs PostgreSQL command-line tools on the jumpbox. No SSH key or
public IP is required. Ask the stack operator for the jumpbox instance ID, then
start an interactive session:

```bash
aws ssm start-session --target <jumpbox-instance-id>
```

From the jumpbox, connect directly to the private database endpoint:

```bash
psql "host=<database-endpoint> port=5432 dbname=<database-name> user=<database-user> sslmode=require"
```

Enter the password when prompted. Type `\q` to exit `psql`, then `exit` to close
the SSM session.

Local mode is intended for administration and diagnostics. Do not store
credentials, exports, or database dumps permanently on the jumpbox.

## Troubleshooting

### `TargetNotConnected`

The instance is not registered with Systems Manager. Check that it is running,
has the SSM-managed instance role, and has outbound network access.

### Local port already in use

Choose another unused local port, for example `15433`, and configure your
database client to use the same port.

### Tunnel opens but the database connection times out

Check the database endpoint and port, and confirm that the database security
group allows traffic from the jumpbox security group.

### Authentication fails

Retrieve the secret again and check the database name and username. RDS may
have rotated or regenerated the password since it was last copied.

## Security notes

- Access is controlled by AWS IAM and audited through Systems Manager.
- The jumpbox requires no inbound security-group rules.
- Never put database passwords directly in shell commands or source-controlled
  configuration.
- Use the jumpbox for database administration and inspection only.
- Prefer read-only database credentials where the task does not require writes.
