from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile


OUTPUT_FILE = Path("DLP_ADVISOR_PLATFORM_ROLE_GUIDE.pptx")

SLIDE_WIDTH = 9_144_000
SLIDE_HEIGHT = 5_143_500


SLIDES = [
    {
        "title": "DLP Advisor Platform",
        "lines": [
            "Role-based guide for using the website effectively.",
            "Designed for Homeowner, Developer, and Lawyer workflows.",
            "Supports defect reporting, repair tracking, legal review, and report generation.",
            "Prepared for FYP presentation, user onboarding, and system briefing.",
        ],
        "font_size": 1_850,
        "accent": "1D4ED8",
    },
    {
        "title": "Platform Purpose and Main Functions",
        "lines": [
            "1. The platform manages property defect cases during the Defect Liability Period (DLP).",
            "2. Homeowners can submit defect complaints with photos and 3D property models.",
            "3. Developers can review complaints, manage repairs, and update the case status.",
            "4. Lawyers can review case details, provide legal comments, and use AI legal support.",
            "5. The system centralizes complaint records, status history, and formal report output.",
            "6. This reduces manual communication and makes the workflow easier to monitor.",
        ],
        "font_size": 1_650,
        "accent": "0F766E",
    },
    {
        "title": "Getting Started",
        "lines": [
            "1. Open the website and register if you are a new user.",
            "2. Choose the correct role during registration: Homeowner, Developer, or Lawyer.",
            "3. Log in using your registered email and password.",
            "4. After login, the system shows a dashboard based on your role.",
            "5. Use the main menu to open reports, cases, 3D viewer, or AI chatbot tools.",
            "6. Always log out after use, especially on public or shared computers.",
        ],
        "font_size": 1_650,
        "accent": "2563EB",
    },
    {
        "title": "Homeowner: Access and Prepare Evidence",
        "lines": [
            "1. Register as a Homeowner and enter the homeowner dashboard after login.",
            "2. Open the 3D Defect Visualizer if you want to inspect the property model first.",
            "3. Upload the property model in GLB format only, with a maximum size of 50MB.",
            "4. Use rotate, zoom, and pan controls to inspect the affected area clearly.",
            "5. Take clear evidence photos before creating the complaint record.",
            "6. Prepare the defect details such as location, category, and description.",
        ],
        "font_size": 1_600,
        "accent": "1E40AF",
    },
    {
        "title": "Homeowner: Submit Report and Track Status",
        "lines": [
            "1. Click Create Report or New Report from the dashboard.",
            "2. Enter the report title, defect category, defect location, and detailed explanation.",
            "3. Upload evidence photos and attach the related 3D model if needed.",
            "4. Submit the report so it can be reviewed by the developer.",
            "5. Open My Cases or Report Status to monitor progress after submission.",
            "6. The status normally changes from Reported to In Progress to Resolved.",
            "7. Use the AI Legal Chatbot to ask about DLP rights, SPA clauses, or next steps.",
        ],
        "font_size": 1_550,
        "accent": "1D4ED8",
    },
    {
        "title": "Developer: Review Incoming Defect Cases",
        "lines": [
            "1. Log in using a Developer account to access the developer dashboard.",
            "2. Open Incoming Reports, Defect List, or the relevant complaint menu.",
            "3. Review each report carefully, including description, location, and severity.",
            "4. Open the uploaded evidence photos to verify the reported issue.",
            "5. Check the 3D model if provided to understand the defect position more clearly.",
            "6. Use the complaint information to plan the required repair action.",
        ],
        "font_size": 1_600,
        "accent": "CA8A04",
    },
    {
        "title": "Developer: Update Repair Progress",
        "lines": [
            "1. Select the case that is currently being repaired or reviewed.",
            "2. Update the case status to reflect the latest repair condition.",
            "3. Use In Progress when repair work has started but is not yet completed.",
            "4. Use Resolved when the defect has been fixed and the case is completed.",
            "5. Add repair notes to record the action taken, progress, or completion details.",
            "6. Save the update so the Homeowner and Lawyer can view the latest case status.",
            "7. Generate a repair report if documentation is needed for record keeping.",
        ],
        "font_size": 1_550,
        "accent": "A16207",
    },
    {
        "title": "Lawyer: Review Case Information",
        "lines": [
            "1. Log in using a Lawyer account to open the lawyer dashboard.",
            "2. Open the Case List to view cases that need legal review.",
            "3. Select a case to read the homeowner complaint and reported defect details.",
            "4. Review the uploaded evidence photos and check the case status history.",
            "5. Read any developer notes to understand the repair response and timeline.",
            "6. Examine the 3D property model if it helps clarify the defect location.",
        ],
        "font_size": 1_600,
        "accent": "9333EA",
    },
    {
        "title": "Lawyer: Legal Support and Documentation",
        "lines": [
            "1. Add legal comments or review notes if the case requires legal interpretation.",
            "2. Use the AI Legal Chatbot for references on DLP rules, SPA clauses, or obligations.",
            "3. Ask focused questions so the chatbot can provide more relevant guidance.",
            "4. Use the chatbot response as supporting reference, not as the only legal conclusion.",
            "5. Generate a legal report if formal documentation is needed for follow-up action.",
            "6. Keep the case record complete so legal review is traceable and well documented.",
        ],
        "font_size": 1_550,
        "accent": "7E22CE",
    },
    {
        "title": "Important Rules and Usage Notes",
        "lines": [
            "1. Upload 3D property files in GLB format only.",
            "2. The maximum upload size allowed by the system is 50MB.",
            "3. Evidence photos should be clear, relevant, and easy to identify.",
            "4. Always confirm that you are using the correct role dashboard before making updates.",
            "5. Use accurate case notes so other roles can understand the current situation.",
            "6. Invalid links or pages display a custom 404 page.",
            "7. Unexpected internal failures display a custom 500 page.",
        ],
        "font_size": 1_550,
        "accent": "DC2626",
    },
    {
        "title": "Summary",
        "lines": [
            "1. Homeowner users report defects, upload evidence, track status, and ask legal questions.",
            "2. Developer users review complaints, manage repairs, update progress, and close cases.",
            "3. Lawyer users examine case records, support legal review, and generate legal documentation.",
            "4. The platform keeps the DLP workflow centralized, traceable, and easier to manage.",
            "5. This improves communication between all parties involved in the defect claim process.",
        ],
        "font_size": 1_650,
        "accent": "1D4ED8",
    },
]


def xml_header() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def paragraph_xml(text: str, size: int, color: str, bold: bool = False) -> str:
    weight = ' b="1"' if bold else ""
    return (
        "<a:p>"
        '<a:pPr algn="l"/>'
        "<a:r>"
        f'<a:rPr lang="en-US" sz="{size}"{weight}>'
        f"<a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill>"
        "</a:rPr>"
        f"<a:t>{escape(text)}</a:t>"
        "</a:r>"
        f'<a:endParaRPr lang="en-US" sz="{size}"/>'
        "</a:p>"
    )


def text_box_xml(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: list[str],
    font_size: int,
    color: str,
    bold: bool = False,
) -> str:
    body = "".join(paragraph_xml(line, font_size, color, bold=bold) for line in paragraphs)
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        '<p:cNvSpPr txBox="1"/>'
        "<p:nvPr/>"
        "</p:nvSpPr>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "<a:noFill/>"
        "</p:spPr>"
        "<p:txBody>"
        '<a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720" anchor="t"/>'
        "<a:lstStyle/>"
        f"{body}"
        "</p:txBody>"
        "</p:sp>"
    )


def filled_rect_xml(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, color: str) -> str:
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        "<p:cNvSpPr/>"
        "<p:nvPr/>"
        "</p:nvSpPr>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        f"<a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill>"
        "<a:ln><a:noFill/></a:ln>"
        "</p:spPr>"
        "<p:style>"
        "<a:lnRef idx=\"0\"><a:schemeClr val=\"accent1\"/></a:lnRef>"
        "<a:fillRef idx=\"0\"><a:schemeClr val=\"accent1\"/></a:fillRef>"
        "<a:effectRef idx=\"0\"><a:schemeClr val=\"accent1\"/></a:effectRef>"
        "<a:fontRef idx=\"minor\"><a:schemeClr val=\"tx1\"/></a:fontRef>"
        "</p:style>"
        "<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>"
        "</p:sp>"
    )


def slide_xml(title: str, lines: list[str], accent: str, index: int, font_size: int) -> str:
    footer = f"Slide {index} of {len(SLIDES)}"
    shapes = [
        filled_rect_xml(2, "Top Bar", 0, 0, SLIDE_WIDTH, 240_000, accent),
        text_box_xml(3, "Title", 520_000, 320_000, 8_100_000, 600_000, [title], 2_800, "17324D", bold=True),
        text_box_xml(4, "Body", 520_000, 1_020_000, 8_050_000, 3_600_000, lines, font_size, "334155"),
        text_box_xml(5, "Footer", 520_000, 4_600_000, 8_050_000, 250_000, [footer], 1_100, "64748B"),
    ]
    return (
        f"{xml_header()}"
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:cSld>"
        "<p:bg><p:bgPr><a:solidFill><a:srgbClr val=\"F8FAFC\"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>"
        "<p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr>"
        "<a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm>"
        "</p:grpSpPr>"
        f'{"".join(shapes)}'
        "</p:spTree>"
        "</p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )


def slide_rels_xml() -> str:
    return (
        f"{xml_header()}"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
        "</Relationships>"
    )


def content_types_xml() -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(SLIDES) + 1)
    )
    return (
        f"{xml_header()}"
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/presProps.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
        '<Override PartName="/ppt/viewProps.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
        '<Override PartName="/ppt/tableStyles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        f"{slide_overrides}"
        "</Types>"
    )


def root_rels_xml() -> str:
    return (
        f"{xml_header()}"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def app_xml() -> str:
    return (
        f"{xml_header()}"
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Codex</Application>"
        "<PresentationFormat>On-screen Show (16:9)</PresentationFormat>"
        f"<Slides>{len(SLIDES)}</Slides>"
        "<Notes>0</Notes><HiddenSlides>0</HiddenSlides><MMClips>0</MMClips>"
        "<ScaleCrop>false</ScaleCrop>"
        "<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\">"
        "<vt:variant><vt:lpstr>Theme</vt:lpstr></vt:variant>"
        "<vt:variant><vt:i4>1</vt:i4></vt:variant>"
        "</vt:vector></HeadingPairs>"
        "<TitlesOfParts><vt:vector size=\"1\" baseType=\"lpstr\">"
        "<vt:lpstr>DLP Advisor Theme</vt:lpstr>"
        "</vt:vector></TitlesOfParts>"
        "<Company/>"
        "<LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>"
        "<HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0000</AppVersion>"
        "</Properties>"
    )


def core_xml() -> str:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        f"{xml_header()}"
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>DLP Advisor Platform Role Guide</dc:title>"
        "<dc:subject>Role-based website usage presentation</dc:subject>"
        "<dc:creator>Codex</dc:creator>"
        "<cp:keywords>DLP Advisor Platform, Homeowner, Developer, Lawyer</cp:keywords>"
        "<dc:description>PowerPoint guide for using the website by role.</dc:description>"
        "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def presentation_xml() -> str:
    slide_ids = []
    rel_index = 2
    for slide_no in range(1, len(SLIDES) + 1):
        slide_ids.append(f'<p:sldId id="{255 + slide_no}" r:id="rId{rel_index}"/>')
        rel_index += 1
    slide_id_xml = "".join(slide_ids)
    return (
        f"{xml_header()}"
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slide_id_xml}</p:sldIdLst>"
        f'<p:sldSz cx="{SLIDE_WIDTH}" cy="{SLIDE_HEIGHT}"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "<p:defaultTextStyle/>"
        "</p:presentation>"
    )


def presentation_rels_xml() -> str:
    rels = [
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
            "slideMasters/slideMaster1.xml",
        )
    ]
    next_id = 2
    for slide_no in range(1, len(SLIDES) + 1):
        rels.append(
            (
                f"rId{next_id}",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                f"slides/slide{slide_no}.xml",
            )
        )
        next_id += 1
    rels.extend(
        [
            (
                f"rId{next_id}",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps",
                "presProps.xml",
            ),
            (
                f"rId{next_id + 1}",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps",
                "viewProps.xml",
            ),
            (
                f"rId{next_id + 2}",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles",
                "tableStyles.xml",
            ),
        ]
    )
    rel_xml = "".join(
        f'<Relationship Id="{rel_id}" Type="{rel_type}" Target="{target}"/>'
        for rel_id, rel_type, target in rels
    )
    return (
        f"{xml_header()}"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rel_xml}"
        "</Relationships>"
    )


def pres_props_xml() -> str:
    return (
        f"{xml_header()}"
        '<p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'saveSubsetFonts="1" autoCompressPictures="1"/>'
    )


def view_props_xml() -> str:
    return (
        f"{xml_header()}"
        '<p:viewPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" lastView="sldView">'
        "<p:normalViewPr><p:restoredLeft sz=\"15620\"/><p:restoredTop sz=\"94660\"/></p:normalViewPr>"
        '<p:gridSpacing cx="780288" cy="780288"/>'
        "</p:viewPr>"
    )


def table_styles_xml() -> str:
    return (
        f"{xml_header()}"
        '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>'
    )


def theme_xml() -> str:
    return (
        f"{xml_header()}"
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="DLP Advisor Theme">'
        "<a:themeElements>"
        "<a:clrScheme name=\"DLP Colors\">"
        "<a:dk1><a:srgbClr val=\"111827\"/></a:dk1>"
        "<a:lt1><a:srgbClr val=\"FFFFFF\"/></a:lt1>"
        "<a:dk2><a:srgbClr val=\"0F172A\"/></a:dk2>"
        "<a:lt2><a:srgbClr val=\"F8FAFC\"/></a:lt2>"
        "<a:accent1><a:srgbClr val=\"1D4ED8\"/></a:accent1>"
        "<a:accent2><a:srgbClr val=\"0F766E\"/></a:accent2>"
        "<a:accent3><a:srgbClr val=\"CA8A04\"/></a:accent3>"
        "<a:accent4><a:srgbClr val=\"9333EA\"/></a:accent4>"
        "<a:accent5><a:srgbClr val=\"DC2626\"/></a:accent5>"
        "<a:accent6><a:srgbClr val=\"2563EB\"/></a:accent6>"
        "<a:hlink><a:srgbClr val=\"2563EB\"/></a:hlink>"
        "<a:folHlink><a:srgbClr val=\"7C3AED\"/></a:folHlink>"
        "</a:clrScheme>"
        "<a:fontScheme name=\"DLP Fonts\">"
        "<a:majorFont><a:latin typeface=\"Calibri\"/><a:ea typeface=\"\"/><a:cs typeface=\"\"/></a:majorFont>"
        "<a:minorFont><a:latin typeface=\"Calibri\"/><a:ea typeface=\"\"/><a:cs typeface=\"\"/></a:minorFont>"
        "</a:fontScheme>"
        "<a:fmtScheme name=\"DLP Format\">"
        "<a:fillStyleLst>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"accent1\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"accent2\"/></a:solidFill>"
        "</a:fillStyleLst>"
        "<a:lnStyleLst>"
        "<a:ln w=\"9525\" cap=\"flat\" cmpd=\"sng\" algn=\"ctr\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:prstDash val=\"solid\"/></a:ln>"
        "<a:ln w=\"25400\" cap=\"flat\" cmpd=\"sng\" algn=\"ctr\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:prstDash val=\"solid\"/></a:ln>"
        "<a:ln w=\"38100\" cap=\"flat\" cmpd=\"sng\" algn=\"ctr\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:prstDash val=\"solid\"/></a:ln>"
        "</a:lnStyleLst>"
        "<a:effectStyleLst>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "</a:effectStyleLst>"
        "<a:bgFillStyleLst>"
        "<a:solidFill><a:schemeClr val=\"lt1\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"lt2\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"accent1\"/></a:solidFill>"
        "</a:bgFillStyleLst>"
        "</a:fmtScheme>"
        "</a:themeElements>"
        "<a:objectDefaults/><a:extraClrSchemeLst/>"
        "</a:theme>"
    )


def slide_master_xml() -> str:
    return (
        f"{xml_header()}"
        '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld name="DLP Advisor Master"><p:bg><p:bgRef idx="1001"><a:schemeClr val="lt1"/></p:bgRef></p:bg>'
        "<p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "</p:spTree></p:cSld>"
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>'
        "<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>"
        "</p:sldMaster>"
    )


def slide_master_rels_xml() -> str:
    return (
        f"{xml_header()}"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
        'Target="../theme/theme1.xml"/>'
        "</Relationships>"
    )


def slide_layout_xml() -> str:
    return (
        f"{xml_header()}"
        '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'type="blank" preserve="1" userDrawn="1">'
        '<p:cSld name="Blank Layout">'
        "<p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "</p:spTree>"
        "</p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sldLayout>"
    )


def slide_layout_rels_xml() -> str:
    return (
        f"{xml_header()}"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    )


def build_package() -> dict[str, str]:
    package = {
        "[Content_Types].xml": content_types_xml(),
        "_rels/.rels": root_rels_xml(),
        "docProps/app.xml": app_xml(),
        "docProps/core.xml": core_xml(),
        "ppt/presentation.xml": presentation_xml(),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(),
        "ppt/presProps.xml": pres_props_xml(),
        "ppt/viewProps.xml": view_props_xml(),
        "ppt/tableStyles.xml": table_styles_xml(),
        "ppt/theme/theme1.xml": theme_xml(),
        "ppt/slideMasters/slideMaster1.xml": slide_master_xml(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": slide_master_rels_xml(),
        "ppt/slideLayouts/slideLayout1.xml": slide_layout_xml(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": slide_layout_rels_xml(),
    }

    for slide_no, slide in enumerate(SLIDES, start=1):
        package[f"ppt/slides/slide{slide_no}.xml"] = slide_xml(
            slide["title"],
            slide["lines"],
            slide["accent"],
            slide_no,
            slide.get("font_size", 1_800),
        )
        package[f"ppt/slides/_rels/slide{slide_no}.xml.rels"] = slide_rels_xml()

    return package


def main() -> None:
    package = build_package()
    with zipfile.ZipFile(OUTPUT_FILE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in package.items():
            archive.writestr(file_name, content)
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
