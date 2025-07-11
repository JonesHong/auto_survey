# THIS FILE IS AUTO-GENERATED BY ini2py.
# DO NOT EDIT THIS FILE MANUALLY.

from configparser import SectionProxy
import os

class ConfigSchema:
    """
    配置架構類，用於處理配置文件的特定區段。

    提供方法來返回屬性名稱和值，並支援敏感信息的遮罩處理。
    """
    def __init__(self, config_section: SectionProxy) -> None:
        """
        初始化 ConfigSchema 實例。

        參數：
            config_section (SectionProxy): 配置文件中的特定區段。
        """
        self._config_section = config_section
        
    def return_properties(self, return_type="list", mask_sensitive=True):
        """
        返回所有 @property 方法的名稱和對應的值。

        參數：
            return_type (str): 指定返回格式，'list' 返回列表，'dict' 返回字典。
            mask_sensitive (bool): 是否對敏感信息進行隱藏處理。

        返回：
            list 或 dict: 包含 @property 名稱和值的列表或字典。
        """
        if return_type == "dict":
            payload = {}
        elif return_type == "list":
            payload = []
        else:
            raise ValueError("Invalid return_type. Must be 'list' or 'dict'.")

        sensitive_keywords = [
            "password", "pwd", "api_token", "token", "appkey", "secret", "key",
        ]

        def mask_value(value):
            """
            對敏感值進行遮罩處理。

            參數：
                value: 要遮罩的值。

            返回：
                str: 遮罩後的值。
            """
            value_str = str(value)
            if len(value_str) > 4:
                return value_str[:2] + "*" * (len(value_str) - 4) + value_str[-2:]
            return value

        for attr_name in dir(self):
            attr = getattr(self.__class__, attr_name, None)
            if isinstance(attr, property):
                try:
                    value = getattr(self, attr_name)
                    if mask_sensitive and any(
                        keyword.lower() in attr_name.lower()
                        for keyword in sensitive_keywords
                    ):
                        value = mask_value(value)
                except Exception as e:
                    # 替換 f-string 為字串連接
                    value = "<Error: " + str(e) + ">"

                if return_type == "dict":
                    payload[attr_name] = value
                elif return_type == "list":
                    # 替換 f-string 為字串連接
                    payload.append(str(attr_name) + ": " + str(value))

        return payload


# ---------- GENERATED CLASSES START ----------
class SystemSchema(ConfigSchema):
    """[System]"""
    def __init__(self, config_section: SectionProxy) -> None:
        super().__init__(config_section)

    @property
    def root_path(self):
        return self._config_section.get('root_path')
    @property
    def openai_api_key(self):
        return self._config_section.get('openai_api_key')
    @property
    def csv_path(self):
        return self._config_section.get('csv_path')
    @property
    def openai_model(self):
        return self._config_section.get('openai_model')
    @property
    def company_name(self):
        return self._config_section.get('company_name')
    @property
    def editor_user(self):
        return self._config_section.get('editor_user')
    @property
    def editor_password(self):
        return self._config_section.get('editor_password')
# ---------- GENERATED CLASSES END ----------