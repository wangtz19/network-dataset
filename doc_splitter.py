import os
import re
from docx import Document
import pandas as pd
import pypandoc
from transformers import AutoTokenizer
from tqdm import tqdm


chinese_num = "零一二三四五六七八九十"
start_pattern = re.compile(r"^[%s]\s*、" % chinese_num # 一、
                           + r"|^[%s]\s*\.\s*" % chinese_num # 一.
                           + r"|^（[%s]）" % chinese_num # （一）
                           + r"|^〔[%s]〕\s*" % chinese_num # 〔一〕
                           + r"|^第[%s]部分\s*" % chinese_num # 第一部分
                           + r"|^[0-9]+\s*\.\s*" # 1.
                           + r"|^[0-9]+\s*、" # 1、
                           + r"|^[0-9]+\s*\)" # 1)
                           + r"|^（[0-9]+）" # （1）
                           + r"|^\([0-9]+\)" # (1)
                           + r"|^〔[0-9]+〕" # 〔1〕
                           + r"|^_*[0-9]+\s*．\s*" # 1．
                           )

pattern_list = [
    re.compile(r"^[%s]\s*、" % chinese_num), # 一、
    re.compile(r"^[%s]\s*\.\s*" % chinese_num), # 一.
    re.compile(r"^（[%s]）" % chinese_num), # （一）
    re.compile(r"^〔[%s]〕\s*" % chinese_num), # 〔一〕
    re.compile(r"^第[%s]部分\s*" % chinese_num), # 第一部分
    re.compile(r"^[0-9]+\s*\.\s*"), # 1.
    re.compile(r"^[0-9]+\s*、"), # 1、
    re.compile(r"^[0-9]+\s*\)"), # 1)
    re.compile(r"^（[0-9]+）"), # （1）
    re.compile(r"^\([0-9]+\)" ), # (1)
    re.compile(r"^〔[0-9]+〕"), # 〔1〕
    re.compile(r"^_*[0-9]+\s*．\s*"), # 1．
]

chinese_punctuations = "，。、；：？！…—·「」『』（）［］【】《》〈〉“”‘’. "
english_punctuations = ",.;:?!…—·\"'()[]{}<>"


def match_and_split_heading(text, pattern=start_pattern):
    match = pattern.match(text)
    if match:
        heading_rank = match.group().strip()
        heading_text = text[match.end():].strip("\n "+chinese_punctuations+english_punctuations)
        return heading_rank, heading_text
    else:
        return None, text.strip("\n "+chinese_punctuations+english_punctuations)


def get_heading_info(text):
    for idx in range(len(pattern_list)):
        heading_rank, heading_text = match_and_split_heading(text, pattern_list[idx])
        if heading_rank:
            return idx, heading_rank, heading_text
    return None, None, text


def split_docx_by_heading(filename, min_sentence_len=2):
    doc_tree = {}
    heading_stack = []
    doc = Document(filename)
    for para in doc.paragraphs:
        if para.style.name.startswith("Heading"):
            level = int(para.style.name[7:].strip())
            heading_stack = heading_stack[:level-1]
            heading_rank, heading_text = match_and_split_heading(para.text)
            if heading_rank is None:
                print("Parse Heading Error: ", para.text)
            heading_stack.append((level, heading_text))
        else:
            if len(heading_stack) > 0 and len(para.text) > 0:
                key = "#".join([x[1] for x in heading_stack])
                if key not in doc_tree:
                    doc_tree[key] = ""
                doc_tree[key] += para.text
    return doc_tree


def split_txt_by_heading(contents, min_sentence_len=2):
    doc_tree = {}
    heading_stack = []
    for line in contents:
        line = line.strip("_\n ")
        if len(line) < min_sentence_len:
            continue
        heading_type, heading_rank, heading_text = get_heading_info(line)
        if heading_type is not None:
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
                doc_tree[key] += line
    return doc_tree


def split_by_heading(filename, min_sentence_len=2):
    file_format = filename.split(".")[-1]
    if file_format == "docx":
        return split_docx_by_heading(filename, min_sentence_len=min_sentence_len)
    elif file_format == "txt":
        with open(filename, "r", encoding="utf-8") as fin:
            contents = fin.readlines()
        return split_txt_by_heading(contents, min_sentence_len=min_sentence_len)
    else:
        raise Exception("Unsupported file format: %s" % file_format)


def doc_to_csv(input_filename, output_filename=None):
    input_format = input_filename.split(".")[-1]
    doc_tree = split_by_heading(input_filename)
    if len(doc_tree) == 0 and input_format == "docx":
        # split from docx failed, try to convert to txt and split again
        txt_contents = pypandoc.convert_file(input_filename, 'plain').split("\n")
        doc_tree = split_txt_by_heading(txt_contents)
    
    # to csv, key is summary, value is content
    df = pd.DataFrame(doc_tree.items(), columns=["summary", "content"])

    # count tokens
    tokenizer = AutoTokenizer.from_pretrained("THUDM/chatglm-6b", trust_remote_code=True)
    df["summary_token_num"] = df["summary"].apply(lambda x: len(tokenizer.tokenize(x)))
    df["content_token_num"] = df["content"].apply(lambda x: len(tokenizer.tokenize(x)))
    df["token_num"] = df["content_token_num"] + df["summary_token_num"]

    if output_filename is None:
        output_filename = input_filename + ".csv"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    df.to_csv(output_filename, index=False, encoding="utf-8")
