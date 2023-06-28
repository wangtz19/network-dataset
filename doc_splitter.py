import os
import re
# from docx import Document
import pandas as pd
import pypandoc
from transformers import AutoTokenizer
from tqdm import tqdm
import opencc
import zipfile
import xml.etree.ElementTree as ET
import fitz
from loader import pdf_to_txt
import json


chinese_num = "零一二三四五六七八九十"
pattern_list = [
    r"^[%s]\s*[、\.]" % chinese_num, # 一、 一.
    r"^[（〔\(][%s][〕）\)]\s*" % chinese_num, #（一）〔一〕(一) 
    r"^第\s*[%s\d]+\s*部分\s*" % chinese_num, # 第一部分
    r"^\d+\s*[、\)〕）]\s*", # 1、1)
    r"^[（\(〔]\d+[）\)〕]", # （1）(1) 〔1〕
    r"^\d+(\.\d+)+\s*", # 1.2.3
    r"^\d+(-\d+)*\s*", # 1-1, 1-1-1, 1-1-1-1 ... 
    r"^第\s*[%s\d]+\s*章\s*" % chinese_num, # 第1章
    r"^_*\d+\s*[．\.]\s+", # 1．1. 
]
start_pattern = re.compile("|".join(pattern_list))

chinese_punctuations = "，。、；：？！…—·「」『』（）［］【】《》〈〉“”‘’. "
english_punctuations = ",.;:?!…—·\"'()[]{}<>"

non_printable_characters = [
    "\u200b", # zero width space
    "\u200e", # left-to-right mark
    "\u200f", # right-to-left mark
    "\u202a", # left-to-right embedding
    "\u202b", # right-to-left embedding
    "\u202c", # pop directional formatting
    "\u202d", # left-to-right override
    "\u202e", # right-to-left override
    "\u2060", # word joiner
    "\u2061", # function application
    "\u2062", # invisible times
    "\u2063", # invisible separator
    "\u2064", # invisible plus
    "\u2066", # left-to-right isolate
    "\u2067", # right-to-left isolate
    "\u2068", # first strong isolate
    "\u2069", # pop directional isolate
    "\u206a", # inhibit symmetric swapping
    "\u206b", # activate symmetric swapping
    "\u206c", # inhibit Arabic form shaping
    "\u206d", # activate Arabic form shaping
    "\u206e", # national digit shapes
    "\u206f", # nominal digit shapes
    "\ufeff", # zero width no-break space
    "\ufff9", # interlinear annotation anchor
    "\ufffa", # interlinear annotation separator
    "\ufffb", # interlinear annotation terminator
]

converter = opencc.OpenCC('t2s.json') # convert Traditional Chinese to Simplified Chinese
tokenizer = AutoTokenizer.from_pretrained("THUDM/chatglm-6b", trust_remote_code=True)


def postprocess(text):
    text = text.replace(" ", "")
    text = text.replace("　", "")
    text = text.strip("\n "+chinese_punctuations+english_punctuations)
    # replace invisible characters
    for ch in non_printable_characters:
        text = text.replace(ch, "")
    # convert to simplified chinese
    text = converter.convert(text)
    return text



def match_and_split_heading(text, pattern=start_pattern):
    text = text.strip()
    match = pattern.match(text)
    if match:
        heading_rank = match.group().strip()
        heading_text = postprocess(text[match.end():])
        return heading_rank, heading_text
    else:
        return None, postprocess(text)


def get_heading_info(text):
    for idx in range(len(pattern_list)):
        heading_rank, heading_text = match_and_split_heading(text, 
                                    re.compile(pattern_list[idx]))
        if heading_rank:
            return idx, heading_rank, heading_text
    return None, None, text


# def split_docx_by_heading(filename, min_sentence_len=2):
#     doc_tree = {}
#     heading_stack = []
#     doc = Document(filename)
#     for para in doc.paragraphs:
#         if para.style.name.startswith("Heading"):
#             level = int(para.style.name[7:].strip())
#             heading_stack = heading_stack[:level-1]
#             heading_rank, heading_text = match_and_split_heading(para.text)
#             if heading_rank is None:
#                 print("Parse Heading Error: ", para.text)
#             heading_stack.append((level, heading_text))
#         else:
#             if len(heading_stack) > 0 and len(para.text) > 0:
#                 key = "#".join([x[1] for x in heading_stack])
#                 if key not in doc_tree:
#                     doc_tree[key] = ""
#                 doc_tree[key] += postprocess(para.text)
#     return doc_tree


HEADING1_LEVEL = 2
OUTLINELVL1_LEVEL = 0

def parse_level(para):
    schema = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        style = para.find("w:pPr", ns).find("w:pStyle", ns)
        level = style.attrib[schema + "val"]
        return int(level) - HEADING1_LEVEL + 1
    except:
        try:
            outlineLvl = para.find("w:pPr", ns).find("w:outlineLvl", ns)
            level = outlineLvl.attrib[schema + "val"]
            return int(level) - OUTLINELVL1_LEVEL + 1
        except:
            return None


def split_docx_from_xml(filename, min_sentence_len=2):
    doc = zipfile.ZipFile(filename).read("word/document.xml")
    root = ET.fromstring(doc)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    body = root.find("w:body", ns)
    paragraphs = body.findall("w:p", ns)
    
    doc_tree = {}
    heading_stack = []
    for para in paragraphs:
        text_elems = para.findall(".//w:t", ns)
        para_text = "".join([t.text for t in text_elems])

        level = parse_level(para)
        if level is not None:
            heading_stack = heading_stack[:level-1]
            heading_rank, heading_text = match_and_split_heading(para_text)
            if heading_rank is None:
                print("Parse Heading Error: ", para_text)
            heading_stack.append((level, heading_text))
        else:
            if len(heading_stack) > 0 and len(para_text) > 0:
                key = "#".join([x[1] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += postprocess(para_text)
    return doc_tree


def split_txt_by_heading(contents, min_sentence_len=2, max_heading_len=20):
    doc_tree = {}
    heading_stack = []
    for line in contents:
        line = line.strip("_\n ")
        if len(line) < min_sentence_len:
            continue
        heading_type, heading_rank, heading_text = get_heading_info(line)
        heading_token_num = len(tokenizer.tokenize(heading_text))
        if heading_type is not None and heading_token_num < max_heading_len:
            for idx in range(len(heading_stack)):
                if heading_stack[idx][0] == heading_type:
                    heading_stack = heading_stack[:idx]
                    break
            heading_stack.append((heading_type, heading_rank, heading_text))
        else:
            if len(heading_stack) > 0:
                key = "#".join([x[2] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += postprocess(line)
    return doc_tree


def check_heading_match(heading_text, paragraphs, start_idx):
    heading_text = heading_text.replace(" ", "")
    paragraph = paragraphs[start_idx].replace(" ", "")
    if heading_text == paragraph:
        return True, start_idx
    if heading_text.startswith(paragraph) and start_idx+1 < len(paragraphs):
        heading_text = heading_text[len(paragraph):]
        return check_heading_match(heading_text, paragraphs, start_idx+1)
    return False, start_idx


def split_pdf_by_heading(filename):
    doc = fitz.open(filename)
    tocs = doc.get_toc()
    paragraphs = "".join(page.get_text() for page in doc).split("\n")
    doc_tree = {}
    heading_stack = []
    outline_idx, para_idx = 0, 0

    while para_idx < len(paragraphs):
        paragraph = paragraphs[para_idx]
        if outline_idx < len(tocs):
            outline_level, outline_text = tocs[outline_idx][:2]
            is_match, start_idx = check_heading_match(outline_text, paragraphs, para_idx)
        else:
            is_match = False
        if is_match:
            outline_idx += 1
            para_idx = start_idx
            level = int(outline_level)
            heading_stack = heading_stack[:level-1]
            heading_rank, heading_text = match_and_split_heading(outline_text)
            if heading_rank is None:
                print("Parse Heading Error: ", paragraph)
            heading_stack.append((level, heading_text))
        else:
            if len(heading_stack) > 0 and len(paragraph) > 0:
                key = "#".join([x[1] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += postprocess(paragraph)
        para_idx += 1
    return doc_tree


def split_by_heading(filename, min_sentence_len=2):
    file_format = filename.split(".")[-1]
    if file_format == "docx":
        # return split_docx_by_heading(filename, min_sentence_len=min_sentence_len)
        doc_tree = split_docx_from_xml(filename, min_sentence_len=min_sentence_len)
        if len(doc_tree) == 0:
            # split from xml failed, try to convert to txt and split again
            txt_contents = pypandoc.convert_file(filename, 'plain').split("\n")
            doc_tree = split_txt_by_heading(txt_contents, min_sentence_len=min_sentence_len)
        return doc_tree
    elif file_format == "pdf":
        doc_tree = split_pdf_by_heading(filename)
        if len(doc_tree) == 0:
            tmp_filename = pdf_to_txt(filename)
            with open(tmp_filename, "r", encoding="utf-8") as fin:
                txt_contents = fin.readlines()
            doc_tree = split_txt_by_heading(txt_contents, min_sentence_len=min_sentence_len)
    elif file_format == "txt":
        with open(filename, "r", encoding="utf-8") as fin:
            contents = fin.readlines()
        return split_txt_by_heading(contents, min_sentence_len=min_sentence_len)
    else:
        raise Exception("Unsupported file format: %s" % file_format)


def doc_to_csv(input_filename, output_filename=None, save_local=True):
    input_format = input_filename.split(".")[-1]
    doc_tree = split_by_heading(input_filename)
    
    # to csv, key is summary, value is content
    df = pd.DataFrame(doc_tree.items(), columns=["summary", "content"])

    # count tokens
    df["summary_token_num"] = df["summary"].apply(lambda x: len(tokenizer.tokenize(x)))
    df["content_token_num"] = df["content"].apply(lambda x: len(tokenizer.tokenize(x)))
    df["token_num"] = df["content_token_num"] + df["summary_token_num"]

    if output_filename is None:
        output_filename = input_filename + ".csv"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    if save_local:
        df.to_csv(output_filename, index=False, encoding="utf-8")
    return df


supported_formats = ["docx", "txt", "pdf"]

def doc_to_csv_batch(input_dir, output_dir=None, save_local=True):
    if output_dir is None:
        output_dir = os.path.join(input_dir, "csv")
    os.makedirs(output_dir, exist_ok=True)
    total_df = pd.DataFrame()
    for root, dirs, files in os.walk(input_dir):
        for filename in tqdm(files):
            if filename.split(".")[-1] in supported_formats:
                input_filename = os.path.join(root, filename)
                output_filename = os.path.join(output_dir, filename + ".csv")
                tmp_df = doc_to_csv(input_filename, output_filename, save_local=save_local)
                total_df = pd.concat([total_df, tmp_df], axis=0)
    if save_local:
        total_df.to_csv(os.path.join(output_dir, "total.csv"), index=False, encoding="utf-8")
    return total_df


def check_heading_match_qa(heading_text, paragraphs, start_idx, if_first=True):
    heading_text = heading_text.replace(" ", "")
    paragraph = paragraphs[start_idx].replace(" ", "")
    if paragraph == heading_text:
        res = "Equal" if if_first else "Contain"
        print(res, heading_text, paragraph)
        return res, start_idx
    if paragraph.startswith(heading_text):
        print("Contain", heading_text, paragraph)
        return "Contain", start_idx
    if heading_text.startswith(paragraph) and start_idx+1 < len(paragraphs):
        heading_text = heading_text[len(paragraph):]
        return check_heading_match(heading_text, paragraphs, start_idx+1, if_first=False)
    print("Fail", heading_text, paragraph)
    return "Fail", start_idx


def split_pdf_by_heading_qa(filename):
    doc = fitz.open(filename)
    tocs = doc.get_toc()
    paragraphs = "".join(page.get_text() for page in doc).replace("\xad", "-").replace("\xa0", "").split("\n")
    doc_tree = {}
    heading_stack = []
    outline_idx, para_idx = 0, 0

    while para_idx < len(paragraphs):
        paragraph = paragraphs[para_idx]
        if outline_idx < len(tocs):
            outline_level, outline_text = tocs[outline_idx][:2]
            is_match, start_idx = check_heading_match(outline_text, paragraphs, para_idx)
        else:
            is_match = "Fail"
        if is_match in ["Equal", "Contain"]:
            outline_idx += 1
            para_idx = start_idx
            level = int(outline_level)
            heading_stack = heading_stack[:level-1]
            heading_rank, heading_text = match_and_split_heading(paragraph)
            if heading_rank is None:
                print("Parse Heading Error: ", paragraph)
                heading_stack.append((level, outline_text))
                key = "#".join([x[1] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += postprocess(heading_text) + "\n"
            elif is_match == "Equal":
                heading_stack.append((level, heading_text))
            elif is_match == "Contain":
                heading_stack.append((level, heading_rank))
                key = "#".join([x[1] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += postprocess(heading_text) + "\n"
        else:
            if len(heading_stack) > 0 and len(paragraph) > 0:
                key = "#".join([x[1] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += postprocess(paragraph) + "\n"
        para_idx += 1
    return doc_tree


def split_qa(doc_tree, output_filename):
    with open(output_filename, "w", encoding="utf-8") as fout:
        for key, value in doc_tree.items():
            value_list = value.split("\n")
            for idx in range(len(value_list)):
                found = False
                if value_list[idx].strip().startswith("答：") or value_list[idx].strip().startswith("解答："):
                    fout.write(json.dumps({
                            "instruction": key,
                            "question": "".join(value_list[:idx]),
                            "answer": "".join(value_list[idx:])
                        }, ensure_ascii=False) + "\n")
                    found = True
                    break
            if not found:
                fout.write(json.dumps({
                        "instruction": key,
                        "question": "".join(value_list),
                        "answer": ""
                    }, ensure_ascii=False) + "\n")