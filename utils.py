import os
import openai
import requests


def set_proxy(proxy="http://dell-1.star:7890"):
    os.environ['http_proxy'] = proxy 
    os.environ['HTTP_PROXY'] = proxy
    os.environ['https_proxy'] = proxy
    os.environ['HTTPS_PROXY'] = proxy


def test_proxy():
    try:
        resp = requests.get("https://www.google.com", timeout=5)
        return resp.status_code == 200
    except:
        return False


def set_openai_key(key_path=".openai-key2"):
    openai.api_key_path = key_path

