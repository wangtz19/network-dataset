import os
import pandas as pd
from gpt_score.gpt3_score import gpt3score
import argparse
from utils import set_proxy, test_proxy, set_openai_key
from qa_generator import split_qa, filter_qa


QUESTION_PROMPT = "请根据以下文本生成问题,尽可能使用简体中文,{aspect}\n\n文本: {context}\n\n问题:\n1."
ANSWER_PROMPT = "请根据以下文本生成答案,尽可能使用简体中文,{aspect}\n\n文本: {context}\n\n问题: {question}\n\n答案:\n"

aspect_question_dict = {
    "informative": "生成的问题应当覆盖文本的关键信息",
    "coherent": "生成的问题应当合乎逻辑",
    "relevant": "生成的问题应当与文本相关",
    "fluent": "生成的问题应当符合语法且读写流畅"
}

aspect_answer_dict = {
    "informative": "生成的答案应当覆盖文本和问题的关键信息",
    "coherent": "生成的答案应当合乎逻辑",
    "relevant": "生成的答案应当与文本和问题相关",
    "fluent": "生成的答案应当符合语法且读写流畅"
}

assert aspect_answer_dict.keys() == aspect_question_dict.keys()
aspect_list = list(aspect_answer_dict.keys())


def evalute_qa(csv_filename):
    df = pd.read_csv(csv_filename)
    for field in ["context", "questions", "answers"]:
        assert field in df.columns, f"Column {field} not found in {csv_filename}"
    
    for asp in aspect_list:
        df[f"{asp}_q_score"] = 0
        df[f"{asp}_a_score"] = 0
        for idx, row in df.iterrows():
            input1 = QUESTION_PROMPT.format(aspect=aspect_question_dict[asp], context=row.context)
            output1 = row.questions
            score1 = gpt3score(input1, output1, gpt3model="davinci003")
            df.loc[idx, f"{asp}_q_score"] = score1

            input2 = ANSWER_PROMPT.format(aspect=aspect_answer_dict[asp], context=row.context, question=row.questions)
            output2 = row.answers
            score2 = gpt3score(input2, output2, gpt3model="davinci003")
            df.loc[idx, f"{asp}_a_score"] = score2
    
    save_filename = csv_filename.replace("-qa-raw.csv", "-eval-qa-raw.csv")
    df.to_csv(save_filename, index=False)
    return save_filename


parser = argparse.ArgumentParser()
parser.add_argument("--input", type=str, required=True, help="input csv filename")
parser.add_argument("--proxy", type=str, default=None, help="proxy address")


def main():
    args = parser.parse_args()

    if args.proxy is not None:
        set_proxy(proxy=args.proxy)
    else:
        set_proxy()
    assert test_proxy(), "proxy is not working"
    set_openai_key()

    save_filename = evalute_qa(args.input)
    save_filename = split_qa(save_filename, aspect_list)
    filter_qa(save_filename)
