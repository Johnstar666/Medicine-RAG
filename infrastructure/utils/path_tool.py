# 为整个工程提供统一的绝对路径
import os

def get_project_root()->str:
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    
    # 向上遍历目录，直到找到包含config目录的目录，这就是项目根目录
    while current_dir:
        if os.path.exists(os.path.join(current_dir, "config")):
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # 已经到达文件系统根目录
            break
        current_dir = parent_dir
    
    # 如果没找到config目录，就使用当前文件的祖父目录作为后备方案
    return os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

def get_abs_path(relative_path:str)->str:
    return os.path.join(get_project_root(), relative_path)

if __name__=='__main__':
    print(get_project_root())
    print(get_abs_path("config/config.txt"))