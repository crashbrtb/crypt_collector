import time
import os
import timeit
import cv2
import numpy as np
import pyautogui
import configparser
import keyboard
import sys
# Remova as importações do tkinter e messagebox se existirem
# import tkinter as tk
# from tkinter import messagebox

import configparser
from language import MESSAGES, LOGS, get_text, LANGUAGES

CONFIG_FILE = "config_crypt.cfg"

def get_current_language():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    lang = "pt"
    if config.has_section("Settings") and config.has_option("Settings", "language"):
        lang = config.get("Settings", "language")
    elif config.has_section("PREFERENCES") and config.has_option("PREFERENCES", "language"):
        lang = config.get("PREFERENCES", "language")
    return lang if lang in LANGUAGES else "pt"

current_language = get_current_language()

def find_image_on_screen(path_image,area,show=False,threshold = 0.8):
    """
    Lê a configuração da área de captura de tela, tira um print,
    encontra uma imagem específica dentro do print e retorna as coordenadas do centro da imagem.
    """
    # 2. Tirar um print da tela conforme as coordenadas
    screenshot = pyautogui.screenshot(region=area)
    screenshot = np.array(screenshot)
    screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    if show:
        cv2.imshow("screenshot", screenshot_gray)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    # 3. Carregar a imagem a ser procurada
    selected_image = cv2.imread(path_image, cv2.IMREAD_GRAYSCALE)
    h, w = selected_image.shape

    # 4. Verificar se a imagem está contida no print da tela
    result = cv2.matchTemplate(screenshot_gray, selected_image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # 5. Se a imagem for encontrada, calcular as coordenadas do centro

    if max_val >= threshold:
        top_left = max_loc
        center_x = top_left[0] + w // 2 + area[0]
        center_y = top_left[1] + h // 2 + area[1]
        return center_x, center_y
    else:
        return None

def click(x, y):
    pyautogui.click(x, y)
    time.sleep(2.0)


def move(x, y):
    pyautogui.moveTo(x, y)
    time.sleep(1.0)

def verify_store_screen(): #verify if store screen was open
    image_path = os.path.join(os_dir, 'images\\bonussale.png')
    result = find_image_on_screen(image_path, screen_area)
    if result is None:
        return False
    else:
        image_path = os.path.join(os_dir, 'images\\x.png')
        posx = find_image_on_screen(image_path, screen_area)  # if store was open, close it
        if posx is None:
            return False
        else:
            click(posx[0], posx[1])
            return True

def search_for_x(): #verify if there is other windows opened
    image_path = os.path.join(os_dir, 'images\\x.png')
    posx = find_image_on_screen(image_path, screen_area)  # if store was open, close it
    if posx is None:
        return False
    else:
        click(posx[0], posx[1])
        return True

def list_files(directorys):

    files = []
    for directory in directorys:
        for raiz, _, files_directory in os.walk(directory):
            for file in files_directory:
                full_path = os.path.join(raiz, file)

                files.append((file, full_path))
    return files

# --- Variável global para controle da interrupção ---
interrupted = False

def on_esc_press():
    """Function called when 'Esc' is pressed."""
    global interrupted
    print(get_text(LOGS, "esc_pressed_interrupting", current_language))
    interrupted = True

# --- Registrar o hotkey ---
# Isso registrará a função para ser chamada quando 'Esc' for pressionado,
# funcionando em segundo plano sem bloquear o script.
keyboard.add_hotkey('esc', on_esc_press)

def sleep_with_countdown(s):
    global interrupted # Acessar a flag global
    s = int(s)
    for i in reversed(range(s + 1)):
        if interrupted: # Verificar antes de cada sleep
            break
        print(i, end=" ")
        time.sleep(1)
    if not interrupted: # Só imprime se não foi interrompido
        print(get_text(LOGS, "time_is_over", current_language))

def open_cript_menu():
    click(cord_click_watchtower[0], cord_click_watchtower[1])
    click(cord_click_cripts[0], cord_click_cripts[1])
    click(center_of_screen[0][0], center_of_screen[0][1])

def search_for_cripts(icons):
    mouse_scroll_counter = 0
    max_scroll = 500
    while mouse_scroll_counter <= max_scroll:
        if interrupted: break
        founded_cript = None
        for icon in icons:
            image_path = os.path.join(os_dir, icon)
            if "rare/2.png" in image_path:#rare/2.png need change ratio to 0.6
                result = find_image_on_screen(image_path, area_cript_icons, False, 0.6)
            else:
                result = find_image_on_screen(image_path, area_cript_icons)
            if result:  # cript found, stop for
                founded_cript = icon
                break
        if founded_cript:  # cript found, click in go button and stop while
            click(cord_click_go_cript[0], cord_click_go_cript[1])
            return founded_cript
            break
        #if cript not found, scroll to next cript
        for i in range(2):
            pyautogui.scroll(-20)
            mouse_scroll_counter = mouse_scroll_counter + 1
            time.sleep(0.2)
        print(mouse_scroll_counter)
        if mouse_scroll_counter == max_scroll: #check if scroll is end
            if search_for_x(): #check if exist wrong windows opened
                print(get_text(LOGS, "wrong_windows_opened", current_language))
            open_cript_menu() #open again cript menu
            for i in range(max_scroll):  # return how many scroll was down
                pyautogui.scroll(+20)
            mouse_scroll_counter = 0  # reset counter
def do_cript(founded_cript):
    click(center_of_screen[0][0], center_of_screen[0][1])
    if 'rare' in founded_cript:
        click(open_button[0], open_button[1])
    image_path = os.path.join(os_dir, "images\\explore.png")
    result = find_image_on_screen(image_path, cord_explore_button)
    if result is None:
        print(get_text(LOGS, "explore_button_not_found", current_language))
        center_control = 1
        while center_control < 9:
            if interrupted: break
            if center_control > 0:
                search_for_x()
            if center_control > 2:
                pyautogui.press('esc')
            click(center_of_screen[center_control][0], center_of_screen[center_control][1])
            # linha para cripta rara
            click(open_button[0], open_button[1])
            image_path = os.path.join(os_dir, "images\\explore.png")
            result = find_image_on_screen(image_path, cord_explore_button)
            if result is None:
                print(get_text(LOGS, "explorer_button_after_store_not_found", current_language))
                center_control = center_control + 1
            else:
                click(result[0],result[1])
                time.sleep(2.0)  # Wait before clicking speed up, as
                return True
                break
    else:
        print(get_text(LOGS, "cripta_encontrada", current_language))
        click(result[0],result[1])
        time.sleep(2.0)  # Wait before clicking speed up, as
        return True

def speedup_march():
        click(cord_speedup_march[0], cord_speedup_march[1])  # click speedup
        if interrupted: return False # Verificar após clique

        result = find_image_on_screen("images\\troopsonthemarch.png.",
                                      cord_click_use_speedups_screen)
        if interrupted: return False # Verificar após busca de imagem

        if result is None:
            print(get_text(LOGS, "error_in_speedy_march", current_language))
            time.sleep(1.0)
            return False # Retorna False em caso de erro
        else:
            for i in range(how_many_speedups):
                if interrupted: break # Verificar antes de cada clique
                click(cord_click_use_speedups[0], cord_click_use_speedups[1])  # acelera
            if interrupted: return False # Verificar após o loop de cliques

            start = timeit.default_timer()
            while True:
                if interrupted: break # Verificar a cada iteração do while
                result = find_image_on_screen("images\\troopsonthemarch.png.", cord_click_use_speedups_screen)
                if result is None:
                    print(get_text(LOGS, "troops_screen_close", current_language))
                    break
                else:
                    print(get_text(LOGS, "waiting_acceleration_screen_close", current_language))
                    # Verificar interrupção antes de um sleep longo
                    for _ in range(5): # Checa a cada segundo durante o sleep de 5s
                        if interrupted: break
                        time.sleep(1.0)
                    if interrupted: break # Sai do while se interrompido durante o sleep
            if interrupted: return False # Verificar após o while

            end = timeit.default_timer()
            print('Duration: %f' % (end - start))
            # Não chama sleep_with_countdown se já interrompido
            if not interrupted:
                sleep_with_countdown(end - start) # sleep_with_countdown já verifica

        # Retorna True se completou sem interrupção e sem erros
        return not interrupted

if __name__ == "__main__":

    # Get the directory where the script is located
    os_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the config file
    config_path = os.path.join(os_dir, 'config_crypt.cfg')
    config = configparser.ConfigParser()
    # Read the config file using the full path
    config.read(config_path)
    if 'COORDINATES' not in config:
        print(f"Error: Could not find [COORDINATES] section in {config_path}")
        # You might want to exit or raise an error here
        exit() # Or raise Exception("Config section not found")
    how_many_cripts = eval(config['COORDINATES']['how_many_cripts'])
    cord_click_watchtower = eval(config['COORDINATES']['cord_click_watchtower'])
    cord_click_cripts = eval(config['COORDINATES']['cord_click_cripts'])
    area_menu_button_go_cript = eval(config['COORDINATES']['area_menu_button_go_cript'])
    cord_speedup_march = eval(config['COORDINATES']['cord_speedup_march'])
    center_of_screen = eval(config['COORDINATES']['center_of_screen'])
    cord_click_use_speedups_screen = eval(config['COORDINATES']['cord_click_use_speedups_screen'])
    cord_click_use_speedups = eval(config['COORDINATES']['cord_click_use_speedups'])
    how_many_speedups = eval(config['COORDINATES']['how_many_speedups'])
    screen_area = eval(config['COORDINATES']['screen_area'])
    open_button = eval(config['COORDINATES']['open_button'])
    test = eval(config['COORDINATES']['test'])
    area_cript_icons = eval(config['COORDINATES']['area_cript_icons'])
    cord_click_go_cript = eval(config['COORDINATES']['cord_click_go_cript'])
    search_cript = eval(config['COORDINATES']['search_cript'])
    rare_cript = eval(config['COORDINATES']['rare_cript'])
    cord_explore_button = eval(config['COORDINATES']['cord_explore_button'])
    counter = 0 #Counter for cript
    errors = 0

    try: # Adicionar try para garantir que a mensagem final seja exibida
        for i in range(how_many_cripts):
            if interrupted: break # Verificar no início de cada loop principal

            # Using specific coordinates as there are many failures when identifying image or text
            # if verify_store_screen():
            if search_for_x():  # verify if store screen is open before start
                print(get_text(LOGS, "store_screen_close", current_language))
            open_cript_menu()
            founded_cript = search_for_cripts(search_cript)
            if founded_cript:
                print("Cript found")
                if search_for_x():  # verify if store screen is open before start
                    print(get_text(LOGS, "store_screen_close", current_language))
                if do_cript(founded_cript):
                    print(get_text(LOGS, "Invading_crypt", current_language))
                    if speedup_march(): # speedup_march agora retorna False se interrompido
                        if interrupted: break # Verificar após cada passo
                        print(get_text(LOGS, "cript_speedup", current_language))
                        counter += 1
                        print(counter, "/", how_many_cripts, " ", get_text(LOGS, "explored_cripts", current_language))
                    # Se speedup_march retornou False (por erro ou interrupção)
                    elif not interrupted: # Só conta como erro se não foi interrupção
                        print(get_text(LOGS, "error_in_speedup_march", current_language))
                        errors = errors + 1
                        print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))

                    elif not interrupted: # Só conta como erro se não foi interrupção
                        print(get_text(LOGS, "error_in_cript", current_language))
                        errors = errors + 1
                        print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))
                elif not interrupted: # Só conta como erro se não foi interrupção
                    print(get_text(LOGS, "error_serch_cript", current_language))
                    errors = errors + 1
                    print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))

                if interrupted: break # Verificar no final do loop

    finally: # Bloco finally garante que isso execute mesmo se ocorrer um erro ou interrupção
        if interrupted:
            # Mantenha o print, ele será capturado pelo launcher
            print("\n------------------------------------")
            print(get_text(LOGS, "cripting_interrupted", current_language))
            print("------------------------------------")
            # Remova a chamada ao messagebox
            # messagebox.showinfo("Interrupção", "Invasão de criptas interrompida")

        # Opcional: remover o hotkey ao final
        if 'keyboard' in sys.modules: # Verifica se o módulo foi importado com sucesso
             try:
                 keyboard.unhook_all_hotkeys()
             except Exception as e:
                 print(f"Erro ao remover hotkeys: {e}", flush=True) # Adiciona flush para garantir visibilidade

        # Remova a destruição da janela raiz do tkinter
        #root.destroy()
        print(get_text(LOGS, "script_finish", current_language), flush=True) # Mensagem final opcional
        sys.exit() # Descomente se quiser que o script termine imediatamente após a interrupção



