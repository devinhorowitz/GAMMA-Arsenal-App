"""Write the Russian string table as windows-1251 (the game reads text/rus in that encoding;
a UTF-8 file shows garbage). Run after changing a string here."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "gamedata", "configs", "text", "rus", "st_arsenal.xml")

STRINGS = [
    ("st_arsenal_title", "Арсенал"),
    ("st_arsenal_cat_pistols", "Пистолеты"),
    ("st_arsenal_cat_smgs", "ПП"),
    ("st_arsenal_cat_shotguns", "Дробовики"),
    ("st_arsenal_cat_rifles", "Автоматы"),
    ("st_arsenal_cat_snipers", "Снайперские"),
    ("st_arsenal_cat_launchers", "Гранатомёты"),
    ("st_arsenal_cat_melee", "Холодное"),
    ("st_arsenal_fire_modes", "Режимы огня"),
    ("st_arsenal_found_count", "Найдено %s из %s"),
    ("st_arsenal_found_on", "Найдено %s: %s"),
    ("st_arsenal_not_found", "Ещё не найдено"),
    ("st_arsenal_found_only", "Только найденные"),
    ("st_arsenal_new_entry", "Новое в Арсенале: %s"),
    ("st_arsenal_back", "Назад"),
    ("st_arsenal_variants", "Варианты:"),
    ("st_arsenal_variant_found", "%s, найдено %s: %s"),
    ("st_arsenal_max", "макс. %s"),
    ("st_arsenal_scopes", "Прицелы:"),
    ("st_arsenal_suppressors", "Глушители:"),
    ("st_arsenal_accessories", "Аксессуары:"),
    ("st_arsenal_parts", "Детали:"),
    ("st_arsenal_builtin", "Встроенный"),
    ("st_arsenal_builtin_on", "Встроенный: %s"),
    ("st_arsenal_builtin_gl", "Встроенный гранатомёт"),
    ("st_arsenal_builtin_gl_on", "Встроенный гранатомёт: %s"),
    ("st_arsenal_builtin_laser", "Встроенный лазер"),
    ("st_arsenal_builtin_laser_on", "Встроенный лазер: %s"),
    ("st_arsenal_makes", "превращает в %s"),
    ("st_arsenal_modes_by_upgrade", "%s (%s после улучшения)"),
    ("st_arsenal_ammo_by_upgrade", "После улучшения: %s"),
    ("st_arsenal_after_upgrade", "после улучшения"),
    ("st_arsenal_magazines", "Магазины:"),
    ("st_arsenal_rounds", "%s патр."),
    ("ui_mcm_menu_arsenal", "Арсенал"),
    ("ui_mcm_arsenal_flat_key", "Открыть Арсенал отдельно"),
    ("ui_mcm_arsenal_flat_key_desc", "Открывает Арсенал в отдельном окне, вне КПК."),
    ("ui_mcm_arsenal_about", "С трёхмерным КПК его страницы выводятся на экран в руке, и значки теряют чёткость. "
                             "По этой клавише Арсенал выводится прямо на экран, так же чётко, как инвентарь."),
    ("st_arsenal_where", "Где найти:"),
    ("st_arsenal_repair_kits", "Ремкомплекты:"),
    ("st_arsenal_carried_by", "Встречается у:"),
    ("st_arsenal_rank_range", "%s – %s"),
    ("st_arsenal_all_ranks", "все ранги"),
    ("st_arsenal_special", "спецотряды"),
    ("st_arsenal_stashes", "В тайниках"),
    ("st_arsenal_stashes_at", "В тайниках, чаще всего: %s"),
    ("st_arsenal_no_source", "Не встречается ни у группировок, ни в тайниках"),
    ("st_arsenal_nimble_from", "У Шустрого, за %s и %s руб."),
    ("st_arsenal_nimble_gets", "Шустрый даёт %s за него и %s руб."),
    ("st_arsenal_made_from", "Собирается: %s + %s"),
    ("st_arsenal_start_kit", "Стартовый набор, %s очков: %s"),
    ("st_arsenal_start_free", "Стартовый набор, бесплатно: %s"),
    ("st_arsenal_start_eco", "%s; только %s"),
    ("st_arsenal_every_faction", "все группировки"),
    ("st_arsenal_camos", "Камуфляж:"),
    ("st_arsenal_camo_found", "Обнаружен"),
    ("st_arsenal_camo_locked", "Ещё не обнаружен"),
    ("st_arsenal_camo_locked_on", "Ещё не обнаружен; бывает на оружии: %s"),
    ("st_arsenal_and_more", "%s и ещё %s"),
    ("ui_mcm_arsenal_count_seen", "Учитывать увиденное оружие"),
    ("ui_mcm_arsenal_count_seen_desc", "Учитывать также оружие в трупе, тайнике или у торговца, когда вы их открываете, а не только то, что вы забрали."),
    ("st_arsenal_risk", "Улучшения R.I.S.K.:"),
    ("st_arsenal_risk_note", "Одно на оружии в исходном виде, от слабого к сильному"),
    ("st_arsenal_risk_bad", "%s (неудача: %s)"),
    ("st_arsenal_risk_same", "на карточке без изменений"),
    ("st_arsenal_risk_accuracy", "Точность"),
    ("st_arsenal_risk_handling", "Удобность"),
    ("st_arsenal_risk_sway", "Раскачка"),
    ("st_arsenal_risk_fire_rate", "Скорострельность"),
    ("st_arsenal_risk_velocity", "Скорость пули"),
    ("st_arsenal_risk_reliability", "Надёжность"),
    ("st_arsenal_risk_recoil", "Контроль отдачи"),
    ("st_arsenal_risk_weight", "Вес"),
    ("st_arsenal_risk_damage", "Урон"),
    # tags for guns that share a name; stat words as the Russian stat card has them
    ("st_arsenal_tag_suppressed", "с глушителем"),
    ("st_arsenal_tag_scoped", "с прицелом"),
    ("st_arsenal_tag_gl", "с ПГ"),
    ("st_arsenal_tag_gl_mount", "под ПГ"),
    ("st_arsenal_tag_auto", "авто"),
    ("st_arsenal_tag_rounds", "%s патр."),
    ("st_arsenal_tag_rpm", "%s ВВМ"),
    ("st_arsenal_tag_accuracy", "точность %s"),
    ("st_arsenal_tag_handling", "удобность %s"),
    ("st_arsenal_tag_damage", "урон %s"),
    ("st_arsenal_tag_speed", "%s м/с"),
    ("st_arsenal_tag_reliability", "надёжность %s"),
    ("st_arsenal_tag_recoil", "контроль отдачи %s"),
    ("st_arsenal_tag_sup_mount", "под глушитель"),
    ("st_arsenal_tag_scope_mount", "под прицел"),
]


def main():
    lines = ['<?xml version="1.0" encoding="windows-1251"?>', "<string_table>"]
    for sid, text in STRINGS:
        lines += ['\t<string id="%s">' % sid, "\t\t<text>%s</text>" % text, "\t</string>"]
    lines.append("</string_table>")
    data = ("\r\n".join(lines) + "\r\n").encode("cp1251")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data)
    print(len(STRINGS), "strings ->", OUT)


if __name__ == "__main__":
    main()
