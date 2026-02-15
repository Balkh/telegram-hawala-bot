import json
import os
import logging

logger = logging.getLogger(__name__)

class LocalizationService:
    _instance = None
    _translations = {}
    _default_lang = "fa"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalizationService, cls).__new__(cls)
            cls._instance._load_translations()
        return cls._instance

    def _load_translations(self):
        locales_dir = os.path.dirname(os.path.dirname(__file__)) + "/locales"
        # نگاشت بین کد زبان و نام فایل
        lang_files = {
            "fa": "fa",  # دری
            "ps": "pa",  # پشتو (فایل pa.json ولی کد زبان ps است)
        }
        for lang_code, file_name in lang_files.items():
            file_path = f"{locales_dir}/{file_name}.json"
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._translations[lang_code] = json.load(f)
                else:
                    logger.warning(f"Translation file not found: {file_path}")
            except Exception as e:
                logger.error(f"Error loading translation {lang_code}: {e}")

    def translate(self, key, lang="fa", **kwargs):
        """
        ترجمه یک کلید به زبان مورد نظر
        استفاده: translate("start.welcome", lang="fa", name="Reza")
        """
        if lang not in self._translations:
            lang = self._default_lang
            
        keys = key.split('.')
        value = self._translations.get(lang, {})
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
                
        if value is None:
            return key
            
        # جایگذاری متغیرها {{variable}}
        if kwargs:
            for k, v in kwargs.items():
                value = value.replace(f"{{{{{k}}}}}", str(v))
                
        return value

# Instance برای استفاده راحت
i18n = LocalizationService()

def _(key, lang="fa", **kwargs):
    return i18n.translate(key, lang, **kwargs)
