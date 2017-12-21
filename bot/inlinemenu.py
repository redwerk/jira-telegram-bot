def build_menu(buttons, n_cols=1, h_buttons=None, f_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if h_buttons:
        menu.insert(0, h_buttons)

    if f_buttons:
        menu.append(f_buttons)

    return menu
