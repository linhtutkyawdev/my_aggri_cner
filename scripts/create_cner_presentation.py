from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import html


OUT_DIR = Path("presentation")
PPTX_PATH = OUT_DIR / "Burmese_Agricultural_CNER_First_Seminar.pptx"
MD_PATH = OUT_DIR / "Burmese_Agricultural_CNER_First_Seminar.md"


slides = [
    {
        "title": "Burmese Agricultural Concept NER using BiLSTM-CRF",
        "bullets": [
            "University of Computer Studies, Yangon",
            "First Seminar",
            "Presented By: [Your Name]",
            "Roll No.: [Your Roll No.]",
            "Batch: [Your Batch]",
            "Supervised By: [Supervisor Name]",
            "Date: [Presentation Date]",
        ],
    },
    {
        "title": "Table of Contents",
        "bullets": [
            "Abstract",
            "Introduction",
            "What is Concept Named Entity Recognition?",
            "Objectives",
            "Related works",
            "Proposed system",
            "Building Burmese agricultural corpus",
            "Tagging and data sanitization",
            "BIO and BIOES transformation",
            "Word and syllable segmentation",
            "Word embedding",
            "BiLSTM-CRF and NCRF++",
            "Implementation and POC results",
            "Conclusion, schedule, and references",
        ],
    },
    {
        "title": "Abstract",
        "bullets": [
            "This work aims to develop a Burmese agricultural Concept Named Entity Recognition system for identifying domain-specific concepts in farmer questions, advisory text, and agricultural articles.",
            "More than 10,000 agricultural sentences were manually tagged and more than half of the sentences were manually reverified for consistency.",
            "The tagged data was sanitized using rule-based tools, retagging instructions, and repeated consistency checks.",
            "The cleaned corpus was transformed into BIO and BIOES sequence-labeling formats at word and syllable levels.",
            "Domain-specific Burmese agricultural embeddings were trained and used in proof-of-concept models with the NCRF++ sequence-labeling framework.",
        ],
    },
    {
        "title": "Introduction",
        "bullets": [
            "Named Entity Recognition is a core NLP task that detects spans of text and assigns them semantic labels.",
            "General NER focuses on labels such as person, location, and organization, while agricultural CNER includes crops, pests, diseases, fertilizers, symptoms, farm operations, measurements, and weather-related concepts.",
            "Burmese agricultural text is challenging because word boundaries are not explicit, spelling variants are common, and domain terms often appear in mixed question-answer style.",
            "A reliable agricultural CNER dataset can support advisory chatbots, search, recommendation systems, question answering, and agricultural knowledge extraction.",
        ],
    },
    {
        "title": "What is Concept NER?",
        "bullets": [
            "Concept NER identifies meaningful domain concepts rather than only proper names.",
            "Example entities include CROP, PEST, DIS, SYM, FERT, FUNG, PESTI, HERB, FARM_OP, CROP_PART, QTY, PERIOD, and WEATHER.",
            "Input text is converted into token-level labels so a model can learn where each concept begins, continues, ends, or appears as a single token.",
            "The final output can be used to extract structured agricultural knowledge from unstructured Burmese text.",
        ],
    },
    {
        "title": "Objectives",
        "bullets": [
            "To construct a cleaned and training-ready Burmese agricultural CNER corpus.",
            "To define clear tagging instructions for agricultural concepts and reduce inconsistent labels.",
            "To transform manually tagged text into BIO and BIOES formats for sequence labeling.",
            "To compare word-level and syllable-level representations for Burmese agricultural NER.",
            "To build domain-specific Burmese agricultural embeddings.",
            "To train proof-of-concept CNER models using NCRF++ and evaluate token accuracy, precision, recall, and F1-score.",
        ],
    },
    {
        "title": "Related Works (1)",
        "bullets": [
            "Lample et al. proposed neural architectures for named entity recognition using LSTM-based sequence models.",
            "Ma and Hovy introduced an end-to-end BiLSTM-CNN-CRF architecture for sequence labeling.",
            "These approaches show that recurrent neural networks can capture contextual information while CRF layers improve valid label transitions.",
            "The present work follows this neural sequence-labeling direction for Burmese agricultural concepts.",
        ],
    },
    {
        "title": "Related Works (2)",
        "bullets": [
            "NCRF++ provides a configurable neural sequence-labeling toolkit for NER, chunking, POS tagging, and related tasks.",
            "It supports word representations, character-level CNN or LSTM features, BiLSTM encoders, and CRF decoding.",
            "This project uses NCRF++ as the proof-of-concept modeling framework because it directly supports BIO and BIOES tagging schemes.",
            "The framework also allows experiments with and without pretrained embeddings.",
        ],
    },
    {
        "title": "Proposed System",
        "bullets": [
            "The proposed system builds a Burmese agricultural CNER pipeline from raw or noisy tagged sentences to model-ready sequence-labeling data.",
            "Manual tagging is guided by agricultural tag definitions and span rules.",
            "Sanitization tools detect format issues, fix repeated term tags, normalize obvious Burmese typos, and convert cleaned tagged lines to CoNLL format.",
            "The model training phase uses NCRF++ with BiLSTM, character CNN, and CRF decoding.",
            "Experiments compare BIO vs BIOES, word vs syllable segmentation, and models with vs without domain embeddings.",
        ],
    },
    {
        "title": "Building Burmese Agricultural Corpus",
        "bullets": [
            "Corpus size: 11,845 cleaned tagged sentence sequences.",
            "Word-level CoNLL data: 247,854 tokens.",
            "Syllable-level CoNLL data: 364,627 tokens.",
            "Train, development, and test split: approximately 80%, 10%, and 10%.",
            "Split sizes: 9,476 train, 1,184 development, and 1,185 test sequences for word-level files.",
            "The same sentence set was converted into BIO word, BIOES word, BIO syllable, and BIOES syllable datasets.",
        ],
    },
    {
        "title": "Tagging and Reverification",
        "bullets": [
            "The tagging instruction file defines operating priorities, output format, cleaning rules, span rules, and allowed agricultural concept tags.",
            "Manual rechecking was performed on more than half of the tagged sentences to improve consistency.",
            "Longest meaningful entity span was preferred unless a phrase contained multiple entity types.",
            "Generic category words were kept as O unless the context referred to a specific agricultural input, organism, crop, operation, or measurement.",
            "Repeated exact term fixes were handled with the tag_fix workflow to reduce repetitive retagging effort.",
        ],
    },
    {
        "title": "Tag Set",
        "bullets": [
            "General entity tags: PER, LOC, ORG.",
            "Crop and plant tags: CROP, VAR, SEED, CROP_PART, FOOD, WEED.",
            "Problem diagnosis tags: PEST, DIS, SYM, PATH, BIOD, ABIOD.",
            "Input and chemical tags: FERT, NUT, PESTI, FUNG, HERB.",
            "Operation and measurement tags: FARM_OP, EQUIP, QTY, COUNT, DIST, TEMP, TIME, PERIOD.",
            "Environment and production tags include WEATHER, HUM, SEASON, SOIL_TYPE, METHOD, PRICE, and YIELD.",
        ],
    },
    {
        "title": "Data Sanitization Tools",
        "bullets": [
            "find_tag_issues.py: detects invalid tags, missing separators, broken segments, and suspicious tagged lines.",
            "fix_tagged_issues.py: repairs common format problems and normalizes training-line structure.",
            "fix_burmese_typos.py: fixes obvious Burmese spelling and OCR-like errors when the intended agricultural meaning is clear.",
            "tag_fix.py: performs exact repeated term retagging across files with dry-run support.",
            "count_tags.py: summarizes tag frequency and helps identify rare or inconsistent labels.",
            "tagged_to_bio.py: converts final tagged text into CoNLL-style BIO/BIOES data.",
        ],
    },
    {
        "title": "BIO and BIOES Formats",
        "bullets": [
            "BIO uses B for the beginning of an entity, I for inside an entity, and O for outside tokens.",
            "BIOES adds E for the end of a multi-token entity and S for a single-token entity.",
            "BIOES can provide clearer boundary information than BIO, especially for multi-token agricultural concepts.",
            "Four datasets were prepared: BIO word, BIOES word, BIO syllable, and BIOES syllable.",
            "These formats make the corpus compatible with NCRF++ sequence-labeling training.",
        ],
    },
    {
        "title": "Word and Syllable Segmentation",
        "bullets": [
            "Word-level segmentation represents each Burmese word or term as a token.",
            "Syllable-level segmentation breaks text into smaller pronunciation-based units.",
            "Syllable-level data creates more tokens and may reduce out-of-vocabulary problems, but it can make entity boundaries harder to learn.",
            "Word-level data in this project produced 247,854 tokens, while syllable-level data produced 364,627 tokens.",
            "Both levels were tested to compare their behavior in agricultural CNER.",
        ],
    },
    {
        "title": "Word Embedding",
        "bullets": [
            "Word embeddings convert tokens into dense numeric vectors that capture distributional context.",
            "Domain-specific embeddings were trained from Burmese agricultural text.",
            "Word embedding file: 60,670 vectors with 200 dimensions.",
            "Syllable embedding file: 17,187 vectors with 200 dimensions.",
            "The embeddings were used as pretrained representations in NCRF++ experiments.",
        ],
    },
    {
        "title": "Why use BiLSTM-CRF?",
        "bullets": [
            "BiLSTM reads each sentence in both forward and backward directions, allowing the model to use left and right context.",
            "Character CNN features help represent subword patterns and spelling variations.",
            "CRF decoding models dependencies between adjacent labels and discourages invalid label transitions.",
            "This architecture is widely used for NER because entity recognition depends on both token context and valid sequence structure.",
        ],
    },
    {
        "title": "NCRF++ Configuration",
        "bullets": [
            "Framework: NCRF++ neural sequence-labeling repository.",
            "Model: BiLSTM word sequence feature extractor with CRF.",
            "Character feature extractor: CNN.",
            "Optimizer: SGD.",
            "Hidden dimension: 200; dropout: 0.5; LSTM layer: 1.",
            "Experiments were run with and without pretrained agricultural embeddings.",
            "Decode configuration generated 10-best prediction outputs for trained models.",
        ],
    },
    {
        "title": "System Flow of Proposed System",
        "bullets": [
            "Raw or previously tagged Burmese agricultural text",
            "Cleaning and format validation",
            "Manual tagging and consistency reverification",
            "Rule-based retagging and sanitization",
            "Word or syllable segmentation",
            "BIO and BIOES CoNLL transformation",
            "Agricultural embedding training",
            "NCRF++ training, decoding, and evaluation",
            "Output: recognized agricultural concept spans and labels",
        ],
    },
    {
        "title": "Implementation",
        "bullets": [
            "Step 1: Prepare cleaned tagged files using the instruction-guided tagging format text@TAG|.",
            "Step 2: Validate and sanitize data with local Python utilities.",
            "Step 3: Convert tagged files into BIO and BIOES CoNLL files.",
            "Step 4: Train Burmese agricultural word and syllable embeddings.",
            "Step 5: Clone and configure NCRF++ in Google Colab.",
            "Step 6: Generate train, development, test, and decode configurations.",
            "Step 7: Train eight proof-of-concept models and compare evaluation results.",
        ],
    },
    {
        "title": "POC Model Results",
        "bullets": [
            "Best word-level result: BIOES word with embeddings achieved test F1 = 0.6802 and token accuracy = 0.8858.",
            "BIO word with embeddings achieved test F1 = 0.6703 and token accuracy = 0.8959.",
            "Models without pretrained embeddings had much lower entity F1 despite reasonable token accuracy.",
            "Syllable-level POC results were weak in the first experiment, suggesting that boundary handling and segmentation require further tuning.",
            "The results indicate that domain embeddings are important for Burmese agricultural CNER.",
        ],
    },
    {
        "title": "Experiment Summary",
        "bullets": [
            "BIOES word + embedding: accuracy 0.8858, precision 0.6972, recall 0.6639, F1 0.6802.",
            "BIO word + embedding: accuracy 0.8959, precision 0.6975, recall 0.6452, F1 0.6703.",
            "BIO word without embedding: accuracy 0.7834, F1 0.0006.",
            "BIO syllable + embedding: accuracy 0.2776, F1 0.0409.",
            "BIO syllable without embedding: accuracy 0.4743, F1 0.0372.",
            "BIOES syllable models did not produce useful entity F1 in the first POC run.",
        ],
    },
    {
        "title": "Conclusion",
        "bullets": [
            "This project created a cleaned Burmese agricultural concept NER corpus with more than 10,000 manually tagged sentences.",
            "The dataset was improved through manual reverification, explicit tagging rules, sanitization tools, and repeated consistency checks.",
            "BIO and BIOES versions were prepared at word and syllable levels for sequence-labeling experiments.",
            "Domain-specific 200-dimensional embeddings were trained for both word and syllable representations.",
            "The first NCRF++ proof-of-concept results show that word-level models with pretrained embeddings are the strongest baseline so far.",
        ],
    },
    {
        "title": "Future Work",
        "bullets": [
            "Continue manual reverification until the full corpus is consistently checked.",
            "Improve rare labels and merge or revise labels with very small support where appropriate.",
            "Tune NCRF++ hyperparameters and train for more iterations.",
            "Compare BiLSTM-CRF with transformer-based Burmese or multilingual models.",
            "Perform per-entity evaluation to identify difficult agricultural concepts.",
            "Build a small demo for extracting concepts from farmer questions or advisory text.",
        ],
    },
    {
        "title": "Thesis Progress Schedule",
        "bullets": [
            "Pre Seminar: literature review and problem definition.",
            "First Seminar: corpus construction, sanitization, embedding training, and NCRF++ POC models.",
            "Second Seminar: full corpus verification and improved baseline experiments.",
            "Third Seminar: model comparison, error analysis, and prototype application.",
            "Defense: finalized dataset, experiments, documentation, and thesis report.",
        ],
    },
    {
        "title": "References",
        "bullets": [
            "Lample, G., Ballesteros, M., Subramanian, S., Kawakami, K., and Dyer, C. Neural Architectures for Named Entity Recognition. NAACL, 2016.",
            "Ma, X. and Hovy, E. End-to-end Sequence Labeling via Bi-directional LSTM-CNNs-CRF. ACL, 2016.",
            "Yang, J. and Zhang, Y. NCRF++: An Open-source Neural Sequence Labeling Toolkit. ACL System Demonstrations, 2018.",
            "Huang, Z., Xu, W., and Yu, K. Bidirectional LSTM-CRF Models for Sequence Tagging. 2015.",
            "Project artifacts: INSTRUCTION.MD, my_agri_cner.ipynb, prepared CoNLL datasets, and Burmese agricultural embedding files.",
        ],
    },
    {
        "title": "Thanks for giving your precious time",
        "bullets": ["Questions and suggestions are welcome."],
    },
]


def xml_escape(text: str) -> str:
    return html.escape(text, quote=True)


def text_body(lines: list[str], font_size: int = 2400) -> str:
    paragraphs = []
    for line in lines:
        paragraphs.append(
            f"""
            <a:p>
              <a:pPr marL="342900" indent="-171450"/>
              <a:r>
                <a:rPr lang="en-US" altLang="my-MM" sz="{font_size}" dirty="0">
                  <a:solidFill><a:srgbClr val="263238"/></a:solidFill>
                  <a:latin typeface="Myanmar Text"/>
                  <a:ea typeface="Myanmar Text"/>
                </a:rPr>
                <a:t>{xml_escape(line)}</a:t>
              </a:r>
            </a:p>
            """
        )
    return "\n".join(paragraphs)


def shape(shape_id: int, x: int, y: int, cx: int, cy: int, text: str, size: int, bold: bool = False, color: str = "263238") -> str:
    bold_attr = ' b="1"' if bold else ""
    return f"""
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{shape_id}" name="TextBox {shape_id}"/>
          <p:cNvSpPr txBox="1"/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" rtlCol="0"/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="en-US" altLang="my-MM" sz="{size}"{bold_attr} dirty="0">
                <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
                <a:latin typeface="Myanmar Text"/>
                <a:ea typeface="Myanmar Text"/>
              </a:rPr>
              <a:t>{xml_escape(text)}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    """


def bullet_shape(shape_id: int, bullets: list[str], compact: bool = False) -> str:
    size = 1850 if compact or len(bullets) > 7 else 2150
    return f"""
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{shape_id}" name="Body {shape_id}"/>
          <p:cNvSpPr txBox="1"/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="914400" y="1524000"/><a:ext cx="10972800" cy="4572000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" rtlCol="0"/>
          <a:lstStyle/>
          {text_body(bullets, size)}
        </p:txBody>
      </p:sp>
    """


def slide_xml(index: int, title: str, bullets: list[str]) -> str:
    compact = len(bullets) > 7
    accent = "2E7D32"
    footer = f"{index}"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FAF7"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Accent"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="274320" cy="6858000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="{accent}"/></a:solidFill>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
      </p:sp>
      {shape(3, 685800, 457200, 11582400, 762000, title, 3100 if len(title) < 56 else 2700, True, "1B5E20")}
      {bullet_shape(4, bullets, compact)}
      {shape(5, 11938000, 6420000, 500000, 250000, footer, 1200, False, "607D3B")}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def presentation_xml() -> str:
    slide_ids = []
    for idx in range(1, len(slides) + 1):
        slide_ids.append(f'<p:sldId id="{255 + idx}" r:id="rId{idx}"/>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldIdLst>
    {''.join(slide_ids)}
  </p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen4x3"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def presentation_rels() -> str:
    rels = []
    for idx in range(1, len(slides) + 1):
        rels.append(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{idx}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{len(slides)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {''.join(rels)}
</Relationships>"""


def content_types() -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for idx in range(1, len(slides) + 1):
        overrides.append(
            f'<Override PartName="/ppt/slides/slide{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  {''.join(overrides)}
</Types>"""


THEME_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Agri CNER">
  <a:themeElements>
    <a:clrScheme name="Agri">
      <a:dk1><a:srgbClr val="1B5E20"/></a:dk1>
      <a:lt1><a:srgbClr val="F8FAF7"/></a:lt1>
      <a:dk2><a:srgbClr val="263238"/></a:dk2>
      <a:lt2><a:srgbClr val="E8F5E9"/></a:lt2>
      <a:accent1><a:srgbClr val="2E7D32"/></a:accent1>
      <a:accent2><a:srgbClr val="795548"/></a:accent2>
      <a:accent3><a:srgbClr val="0277BD"/></a:accent3>
      <a:accent4><a:srgbClr val="F9A825"/></a:accent4>
      <a:accent5><a:srgbClr val="6D4C41"/></a:accent5>
      <a:accent6><a:srgbClr val="00897B"/></a:accent6>
      <a:hlink><a:srgbClr val="0277BD"/></a:hlink>
      <a:folHlink><a:srgbClr val="6A1B9A"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Myanmar Text">
      <a:majorFont><a:latin typeface="Myanmar Text"/><a:ea typeface="Myanmar Text"/><a:cs typeface="Myanmar Text"/></a:majorFont>
      <a:minorFont><a:latin typeface="Myanmar Text"/><a:ea typeface="Myanmar Text"/><a:cs typeface="Myanmar Text"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="AgriFmt">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def write_markdown() -> None:
    parts = []
    for slide in slides:
        parts.append(f"# {slide['title']}\n")
        for bullet in slide["bullets"]:
            parts.append(f"- {bullet}\n")
        parts.append("\n---\n\n")
    MD_PATH.write_text("".join(parts), encoding="utf-8")


def write_pptx() -> None:
    with ZipFile(PPTX_PATH, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types())
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        z.writestr("ppt/presentation.xml", presentation_xml())
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels())
        z.writestr("ppt/theme/theme1.xml", THEME_XML)
        z.writestr(
            "docProps/core.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Burmese Agricultural Concept NER using BiLSTM-CRF</dc:title>
  <dc:creator>Codex</dc:creator>
</cp:coreProperties>""",
        )
        z.writestr(
            "docProps/app.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex generated presentation</Application>
  <Slides>{len(slides)}</Slides>
</Properties>""",
        )
        for idx, slide in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(idx, slide["title"], slide["bullets"]))


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    write_markdown()
    write_pptx()
    print(PPTX_PATH)
    print(MD_PATH)


if __name__ == "__main__":
    main()
