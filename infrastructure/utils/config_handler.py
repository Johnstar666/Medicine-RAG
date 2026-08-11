import yaml
from dotenv import load_dotenv

from infrastructure.utils.path_tool import get_abs_path

# 加载项目根目录 .env（若存在）中的环境变量。
# override=False：已显式设置的环境变量优先于 .env，
# 确保测试注入的 DASHSCOPE_API_KEY（dummy）或用户手动 export 的值不被覆盖。
load_dotenv(get_abs_path(".env"), override=False)

def load_rag_config(config_path:str=get_abs_path("config/rag.yml"),encoding="utf-8"):
    with open(config_path,encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_chroma_config(
    config_path: str = get_abs_path("config/chroma.yml"), encoding: str = "utf-8"
):
    with open(config_path,encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_prompts_config(
    config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"
):
    with open(config_path,encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_pubmed_config(
    config_path: str = get_abs_path("config/pubmed.yml"), encoding: str = "utf-8"
):
    with open(config_path,encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_postgre_config(
    config_path: str = get_abs_path("config/postgre.yml"), encoding: str = "utf-8"
):
    with open(config_path,encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_fastapi_config(
    config_path: str = get_abs_path("config/fastapi.yml"), encoding: str = "utf-8"
):
    with open(config_path,encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

rag_conf=load_rag_config()
chroma_conf=load_chroma_config()
prompts_conf=load_prompts_config()
pubmed_conf=load_pubmed_config()
postgre_conf=load_postgre_config()
fastapi_conf=load_fastapi_config()

if __name__=="__main__":
    pass