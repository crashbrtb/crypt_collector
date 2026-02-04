import pyautogui
import configparser
from pynput import mouse
import tkinter as tk
from screeninfo import get_monitors
import sys
import os
import time
import win32gui
import win32con
import win32com.client
from language import UI, LOGS, MESSAGES, get_text, LANGUAGES

# Corrigindo o caminho do arquivo para usar o diretório do script
script_dir = os.path.dirname(os.path.abspath(__file__))
file = os.path.join(script_dir, 'config_crypt.cfg')
scroll_count = 0

def get_current_language():
    config = configparser.ConfigParser()
    config.read(file)
    lang = "pt"
    if config.has_section("Settings") and config.has_option("Settings", "language"):
        lang = config.get("Settings", "language")
    elif config.has_section("PREFERENCES") and config.has_option("PREFERENCES", "language"):
        lang = config.get("PREFERENCES", "language")
    return lang if lang in LANGUAGES else "pt"

current_language = get_current_language()

# Classe para criar uma janela personalizada que substitui os alertas do PyAutoGUI
class CustomAlert:
    def __init__(self, title, text, button_text=None):
        self.result = None
        self.root = tk.Tk()
        self.root.title(title)
        
        # Centraliza a janela
        window_width = 400
        window_height = 200
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Adiciona o texto
        label = tk.Label(self.root, text=text, wraplength=380, pady=20)
        label.pack(expand=True)
        
        # Adiciona o botão
        button = tk.Button(self.root, text=button_text or get_text(UI, "ok_button", current_language), command=self.on_button_click)
        button.pack(pady=20)
        
        # Configura o protocolo de fechamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Torna a janela modal
        self.root.grab_set()
        self.root.focus_set()
        
        # Inicia o loop principal
        self.root.mainloop()
    
    def on_button_click(self):
        self.result = True
        self.root.destroy()
    
    def on_close(self):
        self.result = None
        self.root.destroy()
        sys.exit(0)  # Encerra o script quando a janela é fechada

def custom_alert(title, text, button="OK"):
    alert = CustomAlert(title, text, button)
    return alert.result

def capture_area():
    def start_selection(event):
        global start_x, start_y
        start_x, start_y = event.x, event.y
        canvas.create_rectangle(start_x, start_y, start_x, start_y, outline='red', tag='selection')

    # Função para atualizar a seleção
    def update_selection(event):
        canvas.coords('selection', start_x, start_y, event.x, event.y)

    # Função para finalizar a seleção
    def end_selection(event):
        global area
        area = (start_x, start_y, event.x, event.y)
        window.destroy()  # Fecha a window

    # Função para lidar com o fechamento da janela
    def on_closing():
        window.destroy()
        sys.exit(0)  # Encerra o script completamente

    # Criando a window
    window = tk.Tk()
    window.title(get_text(UI, "mouse_selection_title", current_language))

    # Fazendo a window ocupar a tela inteira
    window.attributes('-fullscreen', True)

    # Tornando a window transparente
    window.attributes('-alpha', 0.3)

    # Criando o canvas
    canvas = tk.Canvas(window, width=window.winfo_screenwidth(), height=window.winfo_screenheight(), bg='white')
    canvas.pack()

    # Vinculando os eventos do mouse
    canvas.bind("<Button-1>", start_selection)
    canvas.bind("<B1-Motion>", update_selection)
    canvas.bind("<ButtonRelease-1>", end_selection)
    
    # Configurando o protocolo de fechamento da janela
    window.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Executando a window
    window.mainloop()
    return area

def get_click_postition():
    # Exibe uma mensagem para o usuário
    
    with mouse.Events() as events:
        for event in events:
            try:
                if event.button == mouse.Button.left:
                    return (event.x, event.y)
            except:
                pass

def scroll_capture():
    # Exibe uma mensagem para o usuário
    custom_alert(get_text(UI, "scroll_capture_title", current_language), get_text(UI, "scroll_capture_msg", current_language))
    
    scroll_count = 0
    def on_scroll(x, y, dx, dy):
        global scroll_count
        scroll_count += dy

    def on_click(x, y, button, pressed):
        # Se o botão esquerdo do mouse for clicado, interrompe o listener
        if button == mouse.Button.left:
            return False

    # Inicia o listener do mouse
    with mouse.Listener(on_scroll=on_scroll, on_click=on_click) as listener:
        listener.join()
    return scroll_count
        
def get_monitor_resolution():
    monitors = get_monitors()
    resolutions = [(m.width, m.height) for m in monitors]
    res = (0,0,resolutions[0][0],resolutions[0][1])
    config = configparser.ConfigParser()
    config.read(file)

    # Adiciona a verificação e criação da seção aqui
    if not config.has_section('COORDINATES'):
        config.add_section('COORDINATES')

    config.set('COORDINATES', 'screen_area', str(res))

    # Salvar as alterações no arquivo 'position.cfg'
    with open(file, 'w') as f:
        config.write(f)
    return resolutions[0][0],resolutions[0][1]

def get_window_size(window_title):
    """
    Captura o tamanho da janela do Total Battle.
    
    Args:
        window_title (str): Título da janela do Total Battle
        
    Returns:
        tuple: (x, y, width, height) da janela ou None se não encontrar
    """
    try:
        # Encontra o handle da janela pelo título
        hwnd = win32gui.FindWindow(None, window_title)
        
        if hwnd:
            # Obtém o retângulo da janela (left, top, right, bottom)
            rect = win32gui.GetWindowRect(hwnd)
            x = rect[0]
            y = rect[1]
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]               
            return (width, height)
        else:
            print(get_text(LOGS, "window_not_found", current_language).format(window_title))
            return None
    except Exception as e:
        print(get_text(LOGS, "window_size_error", current_language).format(e))
        return None

def calibration(opt, msg, title, type_cap):
    # type_cap: 0 for area, 1 for clicks, 2 for scrolls and 3 for prompt
    cord_click = []
    howmany = int
    
    if type_cap == 3:
        # Implementar um prompt personalizado que encerra o script ao fechar
        # Por enquanto, usamos o PyAutoGUI e verificamos o resultado
        result = pyautogui.prompt(text=msg, title=title, default='')
        
        if result is None:  # Usuário cancelou o prompt
            sys.exit(0)
        howmany = int(result)
    else:
        # Usar nossa função de alerta personalizada
        result = custom_alert(title, msg, "OK")
        if result is None:  # Usuário fechou a janela sem clicar em OK
            sys.exit(0)
            
    if type_cap == 2:  # how many scroll clicks capture
        scroll_capture()
    if type_cap == 1:  # position Capture
        cord_click = get_click_postition()
        #time.sleep(1.5)
        #pyautogui.click(cord_click[0], cord_click[1])
    if type_cap == 0:  # area capture
        cord_click = capture_area()
        pyautogui.click(cord_click[0] + 50, cord_click[1] + 20)

    config = configparser.ConfigParser()
    config.read(file)

    # Adicionar ou atualizar a coordenada no arquivo
    if not config.has_section('COORDINATES'):
        config.add_section('COORDINATES')
    if type_cap == 2:
        config.set('COORDINATES', opt, str(scroll_count*-1))  # inverter sentido da rolagem
    elif type_cap == 3:
        config.set('COORDINATES', opt, str(howmany))
    else:
        if opt == "center_of_screen":
            center_position = [] #Após fazer diversas criptas, as criptas aparecem em locais aleatórios na tela o objetivo do código abaixo é mapear todos os espaços ao lado do centro da tela para procurar pela cripta.
            center = get_window_size('Total Battle')
            width_square_distance = int(center[0]/9)
            height_square_distance = int(center[1]/9)
            posicao = int(center[0]/2), int(center[1]/2)# centro
            center_position.append(posicao)
            pyautogui.click(posicao)
            posicao = int(center[0]/2), int((center[1]/2) + height_square_distance)# acima
            center_position.append(posicao)
            posicao = int(center[0]/2), int((center[1]/2) - height_square_distance)#abaixo
            center_position.append(posicao)
            posicao = int((center[0]/2) + width_square_distance), int(center[1]/2)#direita
            center_position.append(posicao)
            posicao = int((center[0]/2) - width_square_distance), int(center[1]/2)#esquerda
            center_position.append(posicao)
            posicao = int((center[0]/2) + width_square_distance/2), int((center[1]/2) + height_square_distance/2)# diagonal inferior direita
            center_position.append(posicao)
            posicao = int((center[0]/2) - width_square_distance/2), int((center[1]/2) - height_square_distance/2)# diagonal inferior esquerda
            center_position.append(posicao)
            posicao = int((center[0]/2) + width_square_distance/2), int((center[1]/2) - height_square_distance/2)# diagonal superior direita
            center_position.append(posicao)
            posicao = int((center[0]/2) - width_square_distance/2), int((center[1]/2) + height_square_distance/2)# diagonal superior esquerda
            center_position.append(posicao)
            config.set('COORDINATES', opt, str(center_position))
            print(opt,"->",center_position)
        else:
            config.set('COORDINATES', opt, str(cord_click))
            print(opt,"-",cord_click)

    # Salvar as alterações no arquivo 'position.cfg'
    with open(file, 'w') as f:
        config.write(f)

    # Mensagem de sucesso
    if type_cap != 3 and opt != "cord_click_use_speedups":
        custom_alert(get_text(UI, "calibration_title", current_language), get_text(UI, "position_captured", current_language).format(title))
    if opt == "cord_click_use_speedups":
        custom_alert(get_text(UI, "calibration_title", current_language), get_text(UI, "position_captured_finished", current_language).format(title))

def activate_window_by_title(title):
    """Tenta encontrar, restaurar, maximizar e ativar uma janela pelo título usando pywin32."""
    hwnd = None
    try:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            print(get_text(LOGS, "window_found", current_language).format(title, hwnd))

            # 1. Restaurar se estiver minimizada
            if win32gui.IsIconic(hwnd):
                print(get_text(LOGS, "window_minimized", current_language).format(title))
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE) # 9 = SW_RESTORE
                time.sleep(0.5)

            # 2. Maximizar a janela (Opcional, mas ajuda a garantir visibilidade)
            # Comente a linha abaixo se não quiser maximizar
            print(get_text(LOGS, "window_maximizing", current_language).format(title))
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE) # 3 = SW_MAXIMIZE
            time.sleep(0.5)

            # 3. Ativar (trazer para frente) - Usando WScript.Shell que é mais robusto
            print(get_text(LOGS, "window_activating_wscript", current_language).format(title))
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate(title) # Tenta ativar pelo título
                # Alternativa: shell.AppActivate(hwnd) # Tenta ativar pelo HWND se o título falhar
                time.sleep(1.0) # Aumentar um pouco a pausa após ativação

                # Verificação se a janela ativa é a correta
                active_hwnd = win32gui.GetForegroundWindow()
                if active_hwnd == hwnd:
                    print(get_text(LOGS, "window_activated", current_language).format(title))
                    return True
                else:
                    print(get_text(LOGS, "window_activation_failed", current_language).format(win32gui.GetWindowText(active_hwnd), active_hwnd))
                    print(get_text(LOGS, "trying_setforegroundwindow", current_language))
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.5)
                        active_hwnd = win32gui.GetForegroundWindow()
                        if active_hwnd == hwnd:
                             print(get_text(LOGS, "window_activated_setforegroundwindow", current_language).format(title))
                             return True
                        else:
                             print(get_text(LOGS, "setforeground_failed", current_language))
                             return False
                    except Exception as set_fg_e:
                        print(get_text(LOGS, "setforeground_error", current_language).format(set_fg_e))
                        return False

            except Exception as activate_e:
                 print(get_text(LOGS, "wscript_activation_error", current_language).format(activate_e))
                 return False

        else:
            print(get_text(LOGS, "window_not_found", current_language).format(title))
            return False
    except Exception as e:
        # Captura erros gerais, como falha ao encontrar a janela ou interagir
        print(get_text(LOGS, "window_interaction_error", current_language).format(title, e))
        if hwnd:
             print(f"(HWND era: {hwnd})")
        return False

if __name__ == "__main__":
    try:
        # Usar nossa função de alerta personalizada
        result = custom_alert(get_text(UI, "calibration_title", current_language), 
                             get_text(MESSAGES, "calibration_instructions", current_language), 
                             get_text(UI, "start_button", current_language))
        
        if result is None:  # Usuário fechou a janela sem clicar em Iniciar
            sys.exit(0)
        game_window_title = 'Total Battle' # <-- CONFIRME ESTE TÍTULO!
        print(get_text(LOGS, "activating_window", current_language).format(game_window_title))
        # The call below should now work as the function is defined
        if not activate_window_by_title(game_window_title):
            messagebox.showwarning(get_text(UI, "warning_title", current_language), 
                                 get_text(MESSAGES, "window_activation_failed", current_language).format(game_window_title))
            # Decide se quer continuar mesmo assim ou parar
            exit()
            #return # Descomente para parar se a janela não for ativada
        '''#Descomente se quiser testar se as posicoes centrais estão corretas
        for i in range(9):
            teste = [(969, 519), (969, 634), (969, 404), (1184, 519), (754, 519), (1076, 576), (861, 461), (1076, 461), (861, 576)]
            pyautogui.moveTo(teste[i][0], teste[i][1], 2)
        '''

        get_monitor_resolution()

        calibration("cord_click_watchtower", get_text(MESSAGES, "click_watchtower_icon", current_language), "Watchtower", 1)
        calibration("cord_click_cripts", get_text(MESSAGES, "click_cripts_menu", current_language), "Cript Menu", 1)
        calibration("area_cript_icons", get_text(MESSAGES, "select_cript_icon_area", current_language), "Cript icon", 0)
        calibration("area_menu_button_go_cript", get_text(MESSAGES, "select_go_button_area", current_language), "Cript go button", 0)
        calibration("center_of_screen", get_text(MESSAGES, "click_cript_on_map", current_language), "Cript in map", 1)
        calibration("open_button", get_text(MESSAGES, "click_open_button", current_language), "Open Button", 1)
        calibration("verify_if_open_explorer_button", get_text(MESSAGES, "select_explorer_button_area", current_language), "Explorer button icon", 0)
        calibration("cord_speedup_march", get_text(MESSAGES, "click_speedup_button", current_language), "Speedup march", 1)
        calibration("cord_click_use_speedups_screen", get_text(MESSAGES, "select_speedup_icon_area", current_language), "Speedup icon", 0)
        calibration("cord_click_use_speedups", get_text(MESSAGES, "click_use_button", current_language), "Use Speedup", 1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
