"""Assertions for announcement email: send permission, picture hosting and DMARC.

ANNOUNCEMENTS_APP_TEMPLATE has sending and pictures on; PICTURES_ONLY_APP_TEMPLATE has
pictures on and sending off; the committed config has both off.
"""
import json

from tests.unit.test_service_wiring import ANNOUNCEMENT_ENVIRONMENT, _container, _task_definition
from tests.unit.test_synth import (
    ANNOUNCEMENTS_APP_TEMPLATE,
    NO_EMAIL_APP_TEMPLATE,
    PICTURES_ONLY_APP_TEMPLATE,
    PROD_APP_TEMPLATE,
    TEMPLATES,
    _resources,
)

SEND_STATEMENT = {
    "Action": "ses:SendEmail",
    "Condition": {"StringEquals": {"ses:FromAddress": "updates@v3.policyatlas.uk"}},
    "Effect": "Allow",
    "Resource": {"Fn::Join": ["", [
        "arn:", {"Ref": "AWS::Partition"}, ":ses:eu-west-2:111111111111:identity/v3.policyatlas.uk",
    ]]},
}
SUPPRESSION_STATEMENT = {
    "Action": "ses:ListSuppressedDestinations",
    "Effect": "Allow",
    "Resource": "*",
}


def _role_statements(template: dict, family: str) -> list[dict]:
    """Every policy statement attached to the task role of ``family``."""
    role = {"Ref": _task_definition(family, template)["TaskRoleArn"]["Fn::GetAtt"][0]}
    return [
        statement
        for _, policy in _resources(template, "AWS::IAM::Policy")
        if role in policy["Properties"]["Roles"]
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]


def _ses_statements(statements: list[dict]) -> list[dict]:
    return [s for s in statements if "ses:" in json.dumps(s["Action"])]


def _image_bucket_id(template: dict) -> str:
    return next(
        logical_id for logical_id, _ in _resources(template, "AWS::S3::Bucket")
        if logical_id.startswith("EmailImageBucket")
    )


def test_ops_role_may_send_only_as_updates_and_read_suppressions_and_the_api_role_has_no_ses():
    ops = _ses_statements(_role_statements(ANNOUNCEMENTS_APP_TEMPLATE, "policy-atlas-v3-ops"))
    assert ops == [SEND_STATEMENT, SUPPRESSION_STATEMENT]
    assert not _ses_statements(_role_statements(ANNOUNCEMENTS_APP_TEMPLATE, "policy-atlas-v3-api"))
    # Switched off (the committed config): neither statement.
    for family in ("policy-atlas-v3-ops", "policy-atlas-v3-api"):
        assert not _ses_statements(_role_statements(TEMPLATES["app"], family))


def _assert_private_bucket_served_only_by_the_site(template: dict) -> str:
    """Check the picture bucket, its policy and the behaviour; return the bucket id."""
    bucket_id = _image_bucket_id(template)
    bucket = template["Resources"][bucket_id]
    assert bucket["DeletionPolicy"] == "Retain" and bucket["UpdateReplacePolicy"] == "Retain"
    assert bucket["Properties"]["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }
    rules = bucket["Properties"]["BucketEncryption"]["ServerSideEncryptionConfiguration"]
    assert rules[0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"

    distribution_id, distribution = _resources(template, "AWS::CloudFront::Distribution")[0]
    statements = next(
        policy["Properties"]["PolicyDocument"]["Statement"]
        for _, policy in _resources(template, "AWS::S3::BucketPolicy")
        if policy["Properties"]["Bucket"] == {"Ref": bucket_id}
    )
    deny, allow = statements
    assert deny["Effect"] == "Deny" and deny["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}
    assert allow["Effect"] == "Allow"
    assert allow["Principal"] == {"Service": "cloudfront.amazonaws.com"}
    assert allow["Action"] == "s3:GetObject"
    assert f'"Ref": "{distribution_id}"' in json.dumps(allow["Condition"]["StringEquals"]["AWS:SourceArn"])

    config = distribution["Properties"]["DistributionConfig"]
    behavior = next(b for b in config["CacheBehaviors"] if b["PathPattern"] == "/email-images/*")
    assert behavior["AllowedMethods"] == ["GET", "HEAD"]
    assert behavior["ViewerProtocolPolicy"] == "redirect-to-https"
    # The site's own headers policy: the site's Content Security Policy is unchanged.
    assert behavior["ResponseHeadersPolicyId"] == config["DefaultCacheBehavior"]["ResponseHeadersPolicyId"]
    origin = next(o for o in config["Origins"] if o["Id"] == behavior["TargetOriginId"])
    assert origin["DomainName"] == {"Fn::GetAtt": [bucket_id, "RegionalDomainName"]}
    default_origin = next(
        o for o in config["Origins"] if o["Id"] == config["DefaultCacheBehavior"]["TargetOriginId"]
    )
    assert origin["OriginAccessControlId"] != default_origin["OriginAccessControlId"]
    return bucket_id


def test_picture_bucket_is_private_read_only_by_the_site_distribution_and_ops_may_only_add():
    template = ANNOUNCEMENTS_APP_TEMPLATE
    bucket_id = _assert_private_bucket_served_only_by_the_site(template)
    granted = [
        (family, statement)
        for family in ("policy-atlas-v3-ops", "policy-atlas-v3-api")
        for statement in _role_statements(template, family)
        if bucket_id in json.dumps(statement["Resource"])
    ]
    assert granted == [("policy-atlas-v3-ops", {
        "Action": "s3:PutObject",
        "Effect": "Allow",
        "Resource": {"Fn::Join": ["", [{"Fn::GetAtt": [bucket_id, "Arn"]}, "/email-images/*"]]},
    })]


def test_rolling_back_sending_keeps_the_pictures_served_and_removes_every_send_right():
    template = PICTURES_ONLY_APP_TEMPLATE
    bucket_id = _assert_private_bucket_served_only_by_the_site(template)
    for family in ("policy-atlas-v3-ops", "policy-atlas-v3-api"):
        statements = _role_statements(template, family)
        assert not _ses_statements(statements)
        assert not [s for s in statements if bucket_id in json.dumps(s["Resource"])]
    ops = _container(_task_definition("policy-atlas-v3-ops", template))
    assert not {item["Name"] for item in ops["Environment"]} & set(ANNOUNCEMENT_ENVIRONMENT)


def _dmarc_records(template: dict) -> list[dict]:
    return [
        record["Properties"]
        for _, record in _resources(template, "AWS::Route53::RecordSet")
        if record["Properties"]["Name"].startswith("_dmarc.")
    ]


def test_one_dmarc_record_for_the_sender_domain_only_when_email_is_enabled():
    for template, domain in ((TEMPLATES["app"], "v3.policyatlas.uk"), (PROD_APP_TEMPLATE, "policyatlas.uk")):
        records = _dmarc_records(template)
        assert [(r["Name"], r["Type"], r["ResourceRecords"]) for r in records] == [
            (f"_dmarc.{domain}.", "TXT", ['"v=DMARC1; p=none"'])
        ]
    assert not _dmarc_records(NO_EMAIL_APP_TEMPLATE)
