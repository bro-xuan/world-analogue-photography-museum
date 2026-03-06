"""Manufacturer name normalization.

Handles aliases, historical name changes, and brand vs manufacturer mapping.
"""

from __future__ import annotations

# Canonical name -> known aliases (all lowercase for matching)
MANUFACTURER_ALIASES: dict[str, list[str]] = {
    "Nikon": ["nippon kogaku", "nippon kogaku k.k.", "nippon kogaku k. k.", "nikon corporation", "nikon (nippon kogaku k. k.)"],
    "Canon": ["canon camera co.", "canon camera company", "canon inc.", "canon inc"],
    "Minolta": ["chiyoda kogaku", "chiyoda optics", "minolta camera co."],
    "Konica Minolta": ["konica minolta holdings"],
    "Konica": ["konishiroku", "konica corporation"],
    "Olympus": ["olympus optical co.", "olympus corporation", "olympus optical", "om digital solutions", "olympus optical co.,", "olympus optical co., ltd."],
    "Pentax": ["asahi optical", "asahi pentax", "asahi optical co.", "asahi"],
    "Fujifilm": ["fuji photo film", "fuji film", "fuji", "fujifilm holdings"],
    "Kodak": ["eastman kodak", "eastman kodak company", "kodak", "kodak eastman", "kodak's"],
    "Leica": ["ernst leitz", "leitz", "leica camera", "leica camera ag", "leitz (leica)"],
    "Contax": ["contax"],  # Brand by Kyocera/Zeiss Ikon
    "Yashica": ["yashica", "yashica (contax)"],
    "Mamiya": ["mamiya camera", "mamiya digital imaging"],
    "Rollei": ["rollei", "franke & heidecke", "rollei-werke", "rolleiflex", "rollei (franke & heidecke)"],
    "Hasselblad": ["victor hasselblad", "hasselblad"],
    "Polaroid": ["polaroid corporation"],
    "Voigtlander": ["voigtländer", "voigtlaender", "voigtlander"],
    "Zeiss Ikon": ["zeiss ikon", "carl zeiss"],
    "Agfa": ["agfa-gevaert", "agfa", "agfa-ansco"],
    "Ilford": ["ilford photo", "ilford imaging"],
    "Bronica": ["zenza bronica", "bronica"],
    "Graflex": ["graflex inc."],
    "Linhof": ["linhof"],
    "Toyo": ["toyo-view", "toyo field"],
    "Horseman": ["horseman", "komamura"],
    "Ricoh": ["ricoh company", "ricoh imaging", "ricoh co."],
    "Adox": ["adox", "fotowerke dr. c. schleussner"],
    "Sigma": ["sigma corporation"],
    "Tamron": ["tamron co."],
    "Cosina": ["cosina co."],
    "Chinon": ["chinon industries"],
    "Vivitar": ["vivitar"],
    "Lomography": ["lomographische ag", "lomography"],
    "Foma": ["foma bohemia", "foma"],
    "Ferrania": ["film ferrania", "ferrania"],
    "CineStill": ["cinestill film", "cinestill"],
    "Orwo": ["orwo", "filmotec"],
    # Chinese brands
    "Seagull": ["海鸥", "shanghai camera factory", "shanghai seagull", "shanghai camera", "haiou"],
    "Holga": ["holga"],
    "Phenix": ["phenix", "phenix optical", "凤凰", "phoenix", "jiangxi optical"],
    "Great Wall": ["great wall", "great wall camera", "长城"],
    "Pearl River": ["pearl river", "pearl river camera", "珠江", "guangzhou camera", "zhujiang"],
    "Shanghai": ["上海"],
    "Red Flag": ["红旗", "hongqi", "shanghai red flag"],
    "Dong Feng": ["东风", "dongfeng", "east wind"],
    "Huaxia": ["华夏"],
    "Huqiu": ["虎丘", "tiger hill"],
    "Mudan": ["牡丹", "peony", "dandong camera"],
    "Qingdao": ["青岛", "quingdao", "qingdao camera"],
    "Zi Jin Shan": ["紫金山", "zijinshan", "purple mountain", "nanjing optical"],
    "Changjiang": ["长江", "chiangjiang", "yangtze"],
    "Xihu": ["西湖", "west lake"],
    "Hua Zhong": ["华中", "huazhong"],
    "Nanjing": ["南京", "nanjing camera"],
    "Xing Fu": ["幸福", "xingfu", "happiness"],
    "Changle": ["长乐"],
    "Huashan": ["华山"],
    "Tianjin": ["天津", "tianjin camera"],
    "Diana": ["diana", "great wall plastic works", "great wall plastic factory"],
    "Dongfang": ["东方", "dongfang", "orient", "tianjin camera factory"],
    "Youyi": ["友谊", "friendship", "wuxi camera"],
    "Hongmei": ["红梅", "red plum", "changzhou camera"],
    "Kongque": ["孔雀", "peacock"],
    "Baihua": ["百花", "hundred flowers"],
    "Taihu": ["太湖"],
    "Lantian": ["蓝天", "blue sky"],
    "Changhong": ["长虹"],
    "Xingguang": ["星光", "starlight"],
    "Huaying": ["华蓥"],
    "Tianche": ["天池"],
    "Mingjiia": ["明佳"],
    "Huaguang": ["华光"],
    "Ganguang": ["甘光"],
    "Shenlong": ["神龙"],
    "Xiongmao": ["熊猫", "panda"],
    "Tiantan": ["天坛", "temple of heaven"],
    "Tianee": ["天鹅", "swan"],
    "Meigui": ["玫瑰", "rose"],
    "Jindu": ["金都"],
    # Minor Chinese brands (from chinesecamera.com)
    "Wanling": ["万灵"],
    "Sanyou": ["三友"],
    "Wannengda": ["万能达"],
    "Wuyang": ["五羊"],
    "Xianle": ["仙乐"],
    "Qier": ["企尔"],
    "Jiali": ["佳丽"],
    "Guanlong": ["冠龙"],
    "Lier": ["利尔"],
    "Laodong": ["劳动", "labor"],
    "Huaxi": ["华西"],
    "Heping": ["和平", "peace"],
    "Haerbin": ["哈尔滨", "harbin"],
    "Dalai": ["大来"],
    "Qiyi": ["奇异", "奇异相机"],
    "Xinle": ["新乐"],
    "Jinghua": ["景华"],
    "Qumei": ["曲美"],
    "Meihua": ["梅花", "plum blossom"],
    "Meihualu": ["梅花鹿"],
    "Shenyang": ["沈阳"],
    "Haiyan": ["海燕", "petrel"],
    "Panfulai": ["潘福莱", "panflex"],
    "Huanqiu": ["环球", "global"],
    "Fuzhou": ["福州"],
    "Yuejin": ["跃进", "great leap"],
    "Qingnian": ["青年", "youth"],
    "Qiyi July1st": ["七一", "july first"],
    "Fengguang": ["风光", "fengguang"],
    "Feiyan": ["飞燕", "swallow"],
    "Feiyue": ["飞跃"],
    "Bailing": ["百灵"],
    "Bohai": ["渤海"],
    "Changchun": ["长春"],
    "Emei": ["峨眉"],
    "Beijing": ["北京", "beijing camera"],
    "Dalian": ["大连"],
    "Huayi": ["华一"],
    "Chunlei": ["春雷"],
    "Chenguang": ["晨光", "morning light"],
    # Soviet/Russian brands
    "Zenit": ["zenit", "kmz", "krasnogorsky zavod", "krasnogorsk mechanical works", "kmz (zenit)", "mechanical factory of krasnogorsk (kmz)", "mechanical factory of krasnogorsk"],
    "FED": ["fed", "fed factory", "kharkov fed factory"],
    "Kiev": ["kiev", "arsenal", "arsenal factory", "zavod arsenal"],
    "Zorki": ["zorki", "kmz zorki"],
    "LOMO": ["lomo", "leningrad optical mechanical", "lomo plc"],
    "Smena": ["smena"],
    # Eastern European brands
    "Praktica": ["praktica", "pentacon", "veb pentacon", "praktica (kw)"],
    "Exakta": ["exakta", "ihagee", "ihagee dresden", "(ikon veb)"],
    "Meopta": ["meopta", "meopta optics"],
    # Missing Japanese brands
    "Topcon": ["topcon", "tokyo optical", "tokyo kogaku"],
    "Miranda": ["miranda", "miranda camera"],
    "Petri": ["petri", "kuribayashi", "petri camera"],
    # Collectiblend-specific names
    "Balda": ["balda", "balda-werke"],
    "Bell & Howell": ["bell & howell", "bell and howell"],
    "Berning Robot": ["berning robot", "robot"],
    "ICA": ["ica", "ica ag"],
    "Ansco": ["ansco", "ansco division"],
    "Houghton": ["houghton", "houghton (ensign)", "ensign"],
    "Ernemann": ["ernemann", "ernemann-werke"],
    "Keystone": ["keystone", "keystone camera"],
    "Coronet": ["coronet", "coronet camera"],
    "Goerz": ["goerz", "c.p. goerz"],
    "Wirgin": ["wirgin", "wirgin camera"],
    "Riken": ["riken", "riken optical"],
    "Minox": ["minox", "minox gmbh"],
    "Alpa": ["alpa", "pignons (alpa)", "pignons"],
    "Revere": ["revere", "revere camera"],
    "Argus": ["argus", "argus camera"],
}

# Build reverse lookup: lowercase alias -> canonical name
_ALIAS_LOOKUP: dict[str, str] = {}
for canonical, aliases in MANUFACTURER_ALIASES.items():
    _ALIAS_LOOKUP[canonical.lower()] = canonical
    for alias in aliases:
        _ALIAS_LOOKUP[alias.lower()] = canonical

# Canonical manufacturer name -> country of origin
MANUFACTURER_COUNTRIES: dict[str, str] = {
    # Japanese
    "Nikon": "Japan",
    "Canon": "Japan",
    "Minolta": "Japan",
    "Konica Minolta": "Japan",
    "Konica": "Japan",
    "Olympus": "Japan",
    "Pentax": "Japan",
    "Fujifilm": "Japan",
    "Yashica": "Japan",
    "Mamiya": "Japan",
    "Bronica": "Japan",
    "Ricoh": "Japan",
    "Sigma": "Japan",
    "Tamron": "Japan",
    "Cosina": "Japan",
    "Chinon": "Japan",
    "Topcon": "Japan",
    "Miranda": "Japan",
    "Petri": "Japan",
    # German
    "Leica": "Germany",
    "Contax": "Germany",
    "Rollei": "Germany",
    "Voigtlander": "Germany",
    "Zeiss Ikon": "Germany",
    "Linhof": "Germany",
    # Swedish
    "Hasselblad": "Sweden",
    # American
    "Kodak": "USA",
    "Polaroid": "USA",
    "Graflex": "USA",
    "Vivitar": "USA",
    # Belgian/German
    "Agfa": "Germany",
    # British
    "Ilford": "UK",
    # Japanese (Toyo/Horseman)
    "Toyo": "Japan",
    "Horseman": "Japan",
    # Austrian
    "Lomography": "Austria",
    # Czech
    "Foma": "Czech Republic",
    "Meopta": "Czech Republic",
    # Italian
    "Ferrania": "Italy",
    # American
    "CineStill": "USA",
    # German (historical)
    "Orwo": "Germany",
    # Chinese
    "Seagull": "China",
    "Holga": "China",
    "Phenix": "China",
    "Great Wall": "China",
    "Pearl River": "China",
    "Shanghai": "China",
    "Red Flag": "China",
    "Dong Feng": "China",
    "Huaxia": "China",
    "Huqiu": "China",
    "Mudan": "China",
    "Qingdao": "China",
    "Zi Jin Shan": "China",
    "Changjiang": "China",
    "Xihu": "China",
    "Hua Zhong": "China",
    "Nanjing": "China",
    "Xing Fu": "China",
    "Changle": "China",
    "Huashan": "China",
    "Tianjin": "China",
    "Diana": "China",
    "Dongfang": "China",
    "Youyi": "China",
    "Hongmei": "China",
    "Kongque": "China",
    "Baihua": "China",
    "Taihu": "China",
    "Lantian": "China",
    "Changhong": "China",
    "Xingguang": "China",
    "Huaying": "China",
    "Tianche": "China",
    "Mingjiia": "China",
    "Huaguang": "China",
    "Ganguang": "China",
    "Shenlong": "China",
    "Xiongmao": "China",
    "Tiantan": "China",
    "Tianee": "China",
    "Meigui": "China",
    "Jindu": "China",
    "Wanling": "China",
    "Sanyou": "China",
    "Wannengda": "China",
    "Wuyang": "China",
    "Xianle": "China",
    "Qier": "China",
    "Jiali": "China",
    "Guanlong": "China",
    "Lier": "China",
    "Laodong": "China",
    "Huaxi": "China",
    "Heping": "China",
    "Haerbin": "China",
    "Dalai": "China",
    "Qiyi": "China",
    "Qiyi July1st": "China",
    "Fengguang": "China",
    "Feiyan": "China",
    "Feiyue": "China",
    "Bailing": "China",
    "Bohai": "China",
    "Changchun": "China",
    "Emei": "China",
    "Beijing": "China",
    "Dalian": "China",
    "Huayi": "China",
    "Chunlei": "China",
    "Chenguang": "China",
    "Xinle": "China",
    "Jinghua": "China",
    "Qumei": "China",
    "Meihua": "China",
    "Meihualu": "China",
    "Shenyang": "China",
    "Haiyan": "China",
    "Panfulai": "China",
    "Huanqiu": "China",
    "Fuzhou": "China",
    "Yuejin": "China",
    "Qingnian": "China",
    # Soviet/Russian
    "Zenit": "Russia",
    "FED": "Ukraine",
    "Kiev": "Ukraine",
    "Zorki": "Russia",
    "LOMO": "Russia",
    "Smena": "Russia",
    # Eastern European
    "Praktica": "Germany",
    "Exakta": "Germany",
    # Collectiblend manufacturers
    "Balda": "Germany",
    "Bell & Howell": "USA",
    "Berning Robot": "Germany",
    "ICA": "Germany",
    "Ansco": "USA",
    "Houghton": "UK",
    "Ernemann": "Germany",
    "Keystone": "USA",
    "Coronet": "UK",
    "Goerz": "Germany",
    "Wirgin": "Germany",
    "Riken": "Japan",
    "Minox": "Germany",
    "Alpa": "Switzerland",
    "Revere": "USA",
    "Argus": "USA",
}


def normalize_manufacturer(name: str) -> str:
    """Return the canonical manufacturer name, or the original name cleaned up."""
    if not name:
        return name
    cleaned = name.strip()
    # Handle camerawiki parsing bug: infobox text dumped as manufacturer (contains |)
    if "|" in cleaned:
        cleaned = cleaned.split("|")[0].strip()
    result = _ALIAS_LOOKUP.get(cleaned.lower())
    if result:
        return result
    # Strip common suffixes
    for suffix in [" Inc.", " Inc", " Co.", " Ltd.", " Ltd", " Corporation", " Corp.", " AG", " GmbH", " S.A."]:
        if cleaned.endswith(suffix):
            stripped = cleaned[: -len(suffix)].strip()
            result = _ALIAS_LOOKUP.get(stripped.lower())
            if result:
                return result
            return stripped
    return cleaned


def get_manufacturer_country(name: str) -> str | None:
    """Return the country of origin for a manufacturer, or None if unknown."""
    canonical = normalize_manufacturer(name)
    return MANUFACTURER_COUNTRIES.get(canonical)
