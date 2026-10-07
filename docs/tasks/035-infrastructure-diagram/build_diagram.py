"""Render the repository-grounded infrastructure diagram to PDF and editable SVG.

Run through this task's Makefile with a Python runtime containing ReportLab.
Outputs are written to the repository's output/pdf directory.
"""

from html import escape
from pathlib import Path
import argparse
import math
import re
import xml.etree.ElementTree as ET

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[3]
ASSETS = Path(__file__).resolve().parent / "assets"
OUT = ROOT / "output" / "pdf"
OUT.mkdir(parents=True, exist_ok=True)
PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument("--bedrock", action="store_true", help="Render the proposed Bedrock variant.")
BEDROCK = PARSER.parse_args().bedrock
STEM = "policy-atlas-infrastructure" + ("-bedrock-proposed" if BEDROCK else "")
W, H = 1920, 1080
INK, MUTED, LINE = "#232F3E", "#526174", "#627184"
PURPLE, GREEN, BLUE = "#8C4FFF", "#24833B", "#147EBA"
PROPOSED = "#007C83"
C = canvas.Canvas(str(OUT / f"{STEM}.pdf"), pagesize=(W, H))
C.setTitle("Policy Atlas | AWS infrastructure | Imagine Grant Round 2" +
           (" | Proposed Bedrock connection" if BEDROCK else ""))
C.setAuthor("Policy Atlas")
SVG = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<title>Policy Atlas AWS infrastructure</title>',
       '<desc>Core architecture configured in the repository, reviewed 8 September 2026. '
       'Browser access through CloudFront and Cognito; API via ALB to one Fargate task, '
       'with Aurora PostgreSQL and outbound NAT to external services.</desc>']
if BEDROCK:
    SVG.append('<desc>Proposed addition: Amazon Bedrock via existing NAT egress, '
               'authenticated by the ECS task role. Not deployed. Current OpenAI route retained.</desc>')


def _rect(x, y, w, h, fill="#FFFFFF", stroke=None, sw=1.4, dash=False):
    C.setFillColor(HexColor(fill))
    C.setStrokeColor(HexColor(stroke or fill))
    C.setLineWidth(sw)
    C.setDash([7, 5] if dash else [])
    C.rect(x, H-y-h, w, h, fill=1, stroke=bool(stroke))
    SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
               f'stroke="{stroke or "none"}" stroke-width="{sw}" '
               f'stroke-dasharray="{"7 5" if dash else "none"}"/>')


def _text(x, y, text, size=20, color=INK, bold=False, anchor="start"):
    font = "Helvetica-Bold" if bold else "Helvetica"
    width = stringWidth(text, font, size)
    left = x - (width / 2 if anchor == "middle" else width if anchor == "end" else 0)
    assert left >= 0 and left + width <= W, text
    C.setFillColor(HexColor(color))
    C.setFont(font, size)
    C.drawString(left, H-y, text)
    SVG.append(f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" '
               f'font-size="{size}" font-weight="{700 if bold else 400}" '
               f'text-anchor="{anchor}" fill="{color}">{escape(text)}</text>')


def _line(points, color=LINE, arrow=True, dash=False, width=2):
    C.setStrokeColor(HexColor(color))
    C.setLineWidth(width)
    C.setDash([6, 5] if dash else [])
    p = C.beginPath()
    p.moveTo(points[0][0], H-points[0][1])
    for x, y in points[1:]:
        p.lineTo(x, H-y)
    C.drawPath(p)
    SVG.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+
               f'" fill="none" stroke="{color}" stroke-width="{width}" '
               f'stroke-dasharray="{"6 5" if dash else "none"}"/>')
    if arrow:
        x, y = points[-1]
        a = math.atan2(y-points[-2][1], x-points[-2][0])
        corners = [(x,y)] + [(x-10*math.cos(a)+s*4*math.sin(a),
                             y-10*math.sin(a)-s*4*math.cos(a)) for s in (-1,1)]
        C.setFillColor(HexColor(color))
        p = C.beginPath()
        p.moveTo(corners[0][0], H-corners[0][1])
        for px, py in corners[1:]:
            p.lineTo(px, H-py)
        p.close()
        C.drawPath(p, fill=1, stroke=0)
        SVG.append('<polygon points="'+' '.join(f'{px},{py}' for px,py in corners)+f'" fill="{color}"/>')


def _icon(key, x, y, size=56):
    C.drawImage(str(ASSETS / f"{key}.png"), x, H-y-size, size, size, mask="auto")
    xml = (ASSETS / f"{key}.svg").read_text()
    xml = re.sub(r'<\?xml.*?\?>', '', xml)
    xml = re.sub(r'<!--.*?-->', '', xml, flags=re.S)
    root = ET.fromstring(xml)
    # Scope SVG IDs so repeated official icons retain their original appearance.
    prefix = f"{key}_{x}_{y}_"
    for node in root.iter():
        for attr, value in list(node.attrib.items()):
            if attr == "id":
                node.set(attr, prefix + value)
            elif "url(#" in value:
                node.set(attr, value.replace("url(#", f"url(#{prefix}"))
    root.set("x", str(x)); root.set("y", str(y))
    root.set("width", str(size)); root.set("height", str(size))
    SVG.append(ET.tostring(root, encoding="unicode"))


def _label(x, y, text, color=MUTED, size=17):
    width = stringWidth(text, "Helvetica", size)
    _rect(x-6, y-size, width+12, size+7)
    _text(x, y, text, size, color)


def _service(key, cx, y, title, lines, size=56):
    _icon(key, cx-size/2, y, size)
    _text(cx, y+size+27, title, 21, bold=True, anchor="middle")
    for i, text in enumerate(lines):
        _text(cx, y+size+53+i*23, text, 18, MUTED, anchor="middle")


_rect(0, 0, W, H)
_rect(48, 44, 7, 73, "#FF9900")
_text(76, 63, "IMAGINE GRANT ROUND 2", 17, MUTED, True)
_text(74, 108, "Policy Atlas | AWS infrastructure", 39, bold=True)
_text(1872, 62, "Evidence discovery, analysis and synthesis", 20, MUTED, anchor="end")
_text(1872, 94, "Core platform + proposed Bedrock connection" if BEDROCK else
      "Core platform architecture", 18, PROPOSED if BEDROCK else MUTED, anchor="end")

# Standard AWS cloud and VPC boundaries; global services sit outside the VPC.
_rect(260, 150, 1330, 770, stroke=INK, sw=1.8)
_icon("cloud", 278, 166, 37)
_text(329, 193, "AWS Cloud", 23, bold=True)
_text(1566, 191, "Regional workload: Europe (London) / eu-west-2", 18, MUTED, anchor="end")
_rect(307, 445, 1259, 353, "#FCFAFF", PURPLE, 1.6)
_icon("vpc", 322, 453, 28)
_text(364, 475, "Amazon VPC", 21, PURPLE, True)
_text(1545, 475, "Public and private subnets across up to 3 Availability Zones", 16, MUTED, anchor="end")
_rect(330, 493, 228, 280, "#F5FBF5", GREEN)
_text(346, 521, "Public subnets", 18, GREEN, True)
_rect(610, 493, 670, 280, "#F3F9FD", BLUE)
_text(627, 521, "Private subnets", 18, BLUE, True)
_rect(1330, 493, 213, 280, "#F5FBF5", GREEN)
_text(1345, 521, "Public subnets", 18, GREEN, True)

# Request arrows run through whitespace; direction is request/dependency, with responses implicit.
_line([(125, 340), (125, 270), (360, 270)], dash=True)
_label(158, 255, "DNS lookup", size=16)
_line([(167, 375), (510 if BEDROCK else 575, 375),
       (510 if BEDROCK else 575, 261), (617 if BEDROCK else 692, 261)])
_label(349, 362, "Web app / HTTPS")
_line([(695 if BEDROCK else 770, 261), (877 if BEDROCK else 1027, 261)])
_label(710 if BEDROCK else 812, 245, "Private origin / OAC", size=16)
_line([(167, 408), (1285 if BEDROCK else 1557, 408),
       (1285 if BEDROCK else 1557, 261), (1193 if BEDROCK else 1453, 261)], color=PURPLE, dash=True)
_label(1000 if BEDROCK else 1104, 397, "Sign-in / OAuth 2.0 + PKCE", PURPLE, 16)
_line([(125, 475), (125, 600), (408, 600)])
_label(162, 587, "API / HTTPS")
_line([(480, 600), (704, 600)])
_label(550, 582, "API + streams", size=16)
_line([(831, 600), (1052, 600)])
_label(901, 582, "SQL / 5432", size=16)
_line([(770, 710), (770, 737), (1306, 737), (1306, 588), (1401, 588)])
_label(929, 760, "Outbound HTTPS via EC2 NAT", size=17)
_line([(1471, 588), (1645, 588)])
_label(1548, 576, "HTTPS", size=16)

_service("users", 125, 340, "Researchers", ["Web browser"], 64)
_service("route53", 400, 233, "Amazon Route 53", ["DNS / global"], 56)
_service("cloudfront", 650 if BEDROCK else 725, 233, "Amazon CloudFront", ["Web delivery / global"], 56)
_service("s3", 910 if BEDROCK else 1060, 233, "Amazon S3", ["Private React / Vite assets"], 56)
_service("cognito", 1160 if BEDROCK else 1420, 233, "Amazon Cognito", ["User authentication"], 56)
if BEDROCK:
    _rect(1310, 214, 240, 192, "#F0FAFA", PROPOSED, 1.8, dash=True)
    _text(1430, 236, "PROPOSED / NOT DEPLOYED", 13, PROPOSED, True, anchor="middle")
    _service("bedrock", 1430, 250, "Amazon Bedrock", ["AI models + embeddings"], 50)
    _text(1430, 382, "ECS task role / HTTPS via NAT", 15, PROPOSED, anchor="middle")
    _line([(1436, 550), (1436, 538), (1578, 538), (1578, 300), (1550, 300)],
          color=PROPOSED, dash=True, width=2.5)
_service("alb", 444, 566, "Application", ["Load Balancer", "HTTPS entry point"], 58)
_service("fargate", 770, 550, "Amazon ECS / Fargate", ["FastAPI + research engine", "One task / 2 vCPU / 8 GiB"], 62)
_service("aurora", 1084, 550, "Amazon Aurora", ["PostgreSQL / one writer", "Evidence, findings and audit"], 62)
_text(1084, 713, "Encrypted / 7-day backups", 16, MUTED, anchor="middle")
_service("ec2", 1436, 555, "Amazon EC2", ["NAT instances", "Internet egress"], 58)

# External integrations are deliberately outside the AWS cloud boundary.
_rect(1645, 425, 235, 355, "#F7F8FA", "#A6AFBA", dash=True)
_text(1665, 458, "External services", 21, bold=True)
for y, title, subtitle in [(505, "OpenAI (current)" if BEDROCK else "OpenAI", "AI models + embeddings"),
                           (573, "OpenAlex + Overton", "Evidence discovery"),
                           (641, "Publisher websites", "Source documents"),
                           (709, "Langfuse", "AI tracing")]:
    _text(1665, y, title, 19, bold=True)
    _text(1665, y+25, subtitle, 16, MUTED)
_text(1645, 812, "External endpoints have", 16, MUTED)
_text(1645, 835, "their own hosting locations.", 16, MUTED)
if BEDROCK:
    _text(1645, 871, "Bedrock: model and region", 16, PROPOSED)
    _text(1645, 894, "selection subject to evaluation.", 16, PROPOSED)

# Operations are a labelled support band, not an invented request pipeline.
_text(284, 834, "SUPPORTING AWS SERVICES", 15, MUTED, True)
for key, x, title, subtitle in [
    ("secrets", 288, "Secrets Manager", "Task-injected credentials"),
    ("cloudwatch", 625, "Amazon CloudWatch", "Application logs"),
    ("iam", 970, "AWS IAM", "Service and deployment roles"),
    ("ssm", 1300, "Systems Manager", "Config + admin access")]:
    _icon(key, x, 855, 40)
    _text(x+52, 870, title, 18, bold=True)
    _text(x+52, 894, subtitle, 15, MUTED)

_line([(48, 947), (1872, 947)], arrow=False, color="#D9DEE5", width=1)
_text(48, 980, "DELIVERY", 15, MUTED, True)
_text(160, 980, "GitHub Actions + AWS OIDC  >  AWS CDK / CloudFormation  >  migrate  >  one running API task + publish web assets", 19)
_text(48, 1019, "Teal dashed: proposed Bedrock route through existing NAT. Other services retain the current architecture. No infrastructure changes deployed."
      if BEDROCK else "Solid arrows: requests / dependencies; responses implicit. Dashed arrows: DNS / sign-in. Supporting-service links omitted for clarity.", 16, MUTED)
_text(48, 1051, "Repository-based view / 8 September 2026 / Core staging and production pattern; separate AWS accounts.", 15, MUTED)
_text(1872, 1051, "Official AWS Architecture Icons / aws.amazon.com/architecture/icons", 14, MUTED, anchor="end")
C.save()
SVG.append('</svg>')
(OUT / f"{STEM}.svg").write_text('\n'.join(SVG))
print(f"Created diagram in {OUT}")
