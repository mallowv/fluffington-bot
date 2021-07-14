import yaml
from yaml.loader import UnsafeLoader

def get_yaml_val(config_file: str, string: str):
    with open(config_file) as config:
        config = yaml.load(config, Loader=UnsafeLoader)
        
    return config[string]