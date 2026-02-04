import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext # Adicionado scrolledtext
from PIL import Image, ImageTk
import os
import configparser
import subprocess
import sys
import threading # Adicionado threading
import queue     # Adicionado queue
															 
import time # <-- Mantido
import win32gui # <-- Adicione esta linha
import win32con # <-- Adicione esta linha
import win32com.client # <-- Adicione esta linha
from language import UI, LANGUAGES, LOGS, get_text

# --- Configurações ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config_crypt.cfg')
# Atualize o nome do arquivo aqui
TEST_SCRIPT = os.path.join(SCRIPT_DIR, 'crypting.py')
IMAGE_BASE_DIR = os.path.join(SCRIPT_DIR, 'images', 'cript') # Base para common/epic/rare
COMMON_DIR = os.path.join(IMAGE_BASE_DIR, 'common')
EPIC_DIR = os.path.join(IMAGE_BASE_DIR, 'epic')
RARE_DIR = os.path.join(IMAGE_BASE_DIR, 'rare') # <-- Adicione esta linha
ICON_SIZE = (64, 64) # Tamanho dos ícones na interface

def get_current_language():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    # Procura na seção Settings ou PREFERENCES
    lang = "pt"
    if config.has_section("Settings") and config.has_option("Settings", "language"):
        lang = config.get("Settings", "language")
    elif config.has_section("PREFERENCES") and config.has_option("PREFERENCES", "language"):
        lang = config.get("PREFERENCES", "language")
    return lang if lang in LANGUAGES else "pt"
# --- Funções Auxiliares ---

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
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)

            # 2. Maximizar a janela
            print(get_text(LOGS, "maximizing", current_language).format(title))
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.5)

            # 3. Ativar (trazer para frente)
            print(get_text(LOGS, "activating", current_language).format(title))
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate(title)
                time.sleep(1.0)

                active_hwnd = win32gui.GetForegroundWindow()
                if active_hwnd == hwnd:
                    print(get_text(LOGS, "activation_success", current_language).format(title))
                    return True
                else:
                    print(get_text(LOGS, "activation_fail", current_language).format(win32gui.GetWindowText(active_hwnd), active_hwnd))
																																										 
                    print(get_text(LOGS, "trying_setforeground", current_language))
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.5)
                        active_hwnd = win32gui.GetForegroundWindow()
                        if active_hwnd == hwnd:
                             print(get_text(LOGS, "setforeground_success", current_language).format(title))
                             return True
                        else:
                             print(get_text(LOGS, "setforeground_fail", current_language))
                             return False
                    except Exception as set_fg_e:
                        print(get_text(LOGS, "setforeground_error", current_language).format(set_fg_e))
                        return False

            except Exception as activate_e:
                 print(get_text(LOGS, "wscript_error", current_language).format(activate_e))
                 return False

        else:
            print(get_text(LOGS, "window_not_found", current_language).format(title))
            return False
    except Exception as e:
        print(get_text(LOGS, "window_interaction_error", current_language).format(title, e))
															
        if hwnd:
             print(f"(HWND era: {hwnd})")
        return False

def get_image_files(directory):
    """Lista arquivos de imagem (.png, .jpg, .jpeg) em um diretório."""
    files = []
    if not os.path.isdir(directory):
        print(get_text(LOGS, "dir_not_found", current_language).format(directory))
														   
        return files
    for f in os.listdir(directory):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            files.append(os.path.join(directory, f))
    return files

def get_relative_path(full_path):
    """Converte caminho absoluto para relativo à pasta 'cript'."""
    rel_path = os.path.relpath(full_path, SCRIPT_DIR).replace('\\', '/')
    if not rel_path.startswith('images/cript/'):
         parts = full_path.split(os.sep)
         try:
             cript_index = parts.index('cript')
             rel_path = '/'.join(parts[cript_index+1:])
         except ValueError:
              print(get_text(LOGS, "rel_path_error", current_language).format(full_path))
																	   
              return full_path
    return rel_path


# --- Classe da Aplicação ---

class ImageSelectorApp:
    def __init__(self, master):
        global current_language
        self.master = master
        # Atualiza o título da janela com o idioma correto já ao iniciar
							  
        master.title(get_text(UI, "main_title", current_language))
        # Não definir geometria fixa inicialmente, ou ajustar depois
        # master.geometry("600x400")

        self.selected_paths = set()
        self.image_widgets = {}
        self.current_directory = None
        self.cripting_process = None # Para guardar a referência do processo
        self.output_queue = queue.Queue() # Fila para comunicação entre threads
        self.status_window = None # Referência para a janela de status
        self.status_text_widget = None # Referência para o widget de texto

        # --- Layout Principal ---
        # Frame para botões de tipo e seleção
        type_frame = ttk.Frame(master)
        type_frame.pack(pady=10)

        # Frame para seleção de idioma
        lang_frame = ttk.Frame(master)
        lang_frame.pack(pady=(10, 0), anchor='e', padx=10)
																				
        ttk.Label(lang_frame, text=get_text(UI, "language", current_language)).pack(side=tk.LEFT, padx=(0, 5))
        self.language_label = lang_frame.winfo_children()[0]  # Salva referência do label de idioma

        self.language_var = tk.StringVar()
        language_names = {code: name for code, name in LANGUAGES.items()}
        self.language_combo = ttk.Combobox(lang_frame, textvariable=self.language_var,
                                           values=list(language_names.values()),
                                           state="readonly", width=10)
        self.language_combo.pack(side=tk.LEFT)
        # Define o valor inicial com base no idioma salvo
        self.language_var.set(language_names.get(current_language, "Português"))
        self.language_combo.bind("<<ComboboxSelected>>", self.change_language)

        # Botões de tipo de imagem
        self.common_button = ttk.Button(type_frame, text=get_text(UI, "btn_common", current_language), command=lambda: self.load_images(COMMON_DIR))
        self.common_button.pack(side=tk.LEFT, padx=5)
        self.epic_button = ttk.Button(type_frame, text=get_text(UI, "btn_epic", current_language), command=lambda: self.load_images(EPIC_DIR))
        self.epic_button.pack(side=tk.LEFT, padx=5)
        self.rare_button = ttk.Button(type_frame, text=get_text(UI, "btn_rare", current_language), command=lambda: self.load_images(RARE_DIR))
        self.rare_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(type_frame, text=get_text(UI, "btn_calibrate", current_language), command=self.run_calibration).pack(side=tk.LEFT, padx=5)

        # Frame para exibir os ícones (com scroll)
        self.icon_canvas = tk.Canvas(master, borderwidth=0, background="#ffffff")
        self.icon_frame = ttk.Frame(self.icon_canvas, style='My.TFrame') # Frame dentro do canvas
        self.scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.icon_canvas.yview)
        self.icon_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.icon_canvas.pack(side="left", fill="both", expand=True)
        self.icon_canvas.create_window((4,4), window=self.icon_frame, anchor="nw", tags="self.icon_frame")

        self.icon_frame.bind("<Configure>", self.on_frame_configure)

                # Adiciona o rodapé com link para e-mail no final de tudo
        # Usando um frame separado para garantir que fique no fundo

        footer_frame = ttk.Frame(master)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 2))
        footer_label = ttk.Label(footer_frame, text=get_text(UI, "developed_by", current_language))
        footer_label.pack(side=tk.LEFT)
        email_label = ttk.Label(footer_frame, text="Crash BR", foreground="blue", cursor="hand2")
        email_label.pack(side=tk.LEFT)
        email_label.bind("<Button-1>", lambda e: self.open_email())

        # Estilo para o frame (opcional, para visualização)
        style = ttk.Style()
        style.configure('My.TFrame', background='white')

        # Botão Play
        self.play_button = ttk.Button(master, text=get_text(UI, "btn_play", current_language), command=self.run_script)
        self.play_button.pack(pady=(0, 5), side=tk.BOTTOM)

        self.select_all_button = ttk.Button(master, text=get_text(UI, "btn_select_all", current_language), command=self.select_all_visible)
        self.select_all_button.pack(pady=(0, 10), side=tk.BOTTOM)

        qty_frame = ttk.Frame(master)
        qty_frame.pack(pady=(0, 10), side=tk.BOTTOM)
        
        self.qty_label = ttk.Label(qty_frame, text=get_text(UI, "lbl_crypt_qty", current_language))
        self.qty_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Variável para armazenar o valor
        self.how_many_cripts_var = tk.StringVar()
        
        # Registra a função de validação
        vcmd = (master.register(self.validate_numeric_input), '%P')
        
        # Cria a caixa de texto com validação
        self.how_many_cripts_entry = ttk.Entry(qty_frame, width=4, textvariable=self.how_many_cripts_var, validate="key", validatecommand=vcmd)
        self.how_many_cripts_entry.pack(side=tk.LEFT)
        
        # Carrega o valor inicial do arquivo de configuração
        self.load_initial_how_many_cripts()

        # Carrega imagens 'epic' por padrão
        self.load_images(EPIC_DIR)

        # Lidar com o fechamento da janela principal
        master.protocol("WM_DELETE_WINDOW", self.on_main_window_close)
        

        # A definição do método on_frame_configure estava aqui dentro, o que é incorreto.
        # Remova a definição daqui.
    def open_email(self):
        """Abre o cliente de e-mail padrão com o endereço de e-mail."""
        import webbrowser
        webbrowser.open('mailto:crashbrtb@gmail.com')
    def change_language(self, event=None):
        global current_language
        selected_lang_name = self.language_var.get()
        # Descobre o código do idioma pelo nome
        for code, name in LANGUAGES.items():
            if name == selected_lang_name:
                current_language = code
                break
        # Salva no config
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        if not config.has_section('Settings'):
            config.add_section('Settings')
        config.set('Settings', 'language', current_language)
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        # Atualiza textos da interface imediatamente
        self.update_ui_language()

    def update_ui_language(self):
        # Atualiza todos os textos da interface conforme o idioma selecionado
        self.master.title(get_text(UI, "main_title", current_language))
        self.language_label.config(text=get_text(UI, "language", current_language))
        self.language_combo.set(get_text(UI, "language", current_language))
        self.play_button.config(text=get_text(UI, "btn_play", current_language))
        self.select_all_button.config(text=get_text(UI, "btn_select_all", current_language))
        self.qty_label.config(text=get_text(UI, "lbl_crypt_qty", current_language))
        self.common_button.config(text=get_text(UI, "btn_common", current_language))
        self.epic_button.config(text=get_text(UI, "btn_epic", current_language))
        self.rare_button.config(text=get_text(UI, "btn_rare", current_language))
        # Repita para todos os widgets relevantes

    def validate_numeric_input(self, value):
        """Valida se a entrada contém apenas números e tem no máximo 3 dígitos."""
        if value == "":
            return True  # Permite campo vazio durante a digitação
        if not value.isdigit():
            return False  # Rejeita caracteres não numéricos
        if len(value) > 3:
            return False  # Limita a 3 dígitos
        return True
    # Coloque a definição do método aqui, no nível da classe

    def load_initial_how_many_cripts(self):
    #"""Carrega o valor inicial de how_many_cripts do arquivo de configuração."""
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            
            if 'COORDINATES' in config and 'how_many_cripts' in config['COORDINATES']:
                value = config['COORDINATES']['how_many_cripts']
                self.how_many_cripts_var.set(value)
            else:
                # Valor padrão se não encontrar no arquivo
                self.how_many_cripts_var.set("5")
        except Exception as e:
            print(get_text(LOGS, "config_load_error", current_language).format(e))
															  
            self.how_many_cripts_var.set("5")  # Valor padrão em caso de erro

    def on_frame_configure(self, event):
        '''Reseta a scroll region para abranger o frame interno'''
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))

    def create_status_window(self):
        """Cria e configura a janela de status."""
        if self.status_window and self.status_window.winfo_exists():
            self.status_window.lift() # Traz para frente se já existir
            return

        self.status_window = tk.Toplevel(self.master)
							  
        self.status_window.title(get_text(UI, "status_title", current_language))
        # Definir tamanho inicial pequeno
        self.status_window.geometry("400x250")

        # Posicionar no canto inferior direito (aproximado)
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x_pos = screen_width - 410 # 400 + margem
        y_pos = screen_height - 240 # 200 + margem + barra de tarefas aprox.
        self.status_window.geometry(f"+{x_pos}+{y_pos}")

        self.status_window.attributes("-topmost", True) # Manter no topo

        # Adicionar área de texto com scroll
        self.status_text_widget = scrolledtext.ScrolledText(
            self.status_window, wrap=tk.WORD, state='disabled' # Inicia desabilitado para escrita
        )
        self.status_text_widget.pack(expand=True, fill='both', padx=5, pady=5)

        # Lidar com o fechamento da janela de status
        self.status_window.protocol("WM_DELETE_WINDOW", self.on_status_window_close)

    def update_status_window(self):
        """Verifica a fila e atualiza o widget de texto."""
        try:
            while True: # Processa todas as mensagens na fila
                line = self.output_queue.get_nowait()
                if line is None: # Sinal de fim do processo
										  
                    self.append_to_status(get_text(LOGS, "script_finished", current_language))
                    self.cripting_process = None # Limpa referência
                    return # Para de verificar a fila para esta execução
                else:
                    self.append_to_status(line)
        except queue.Empty:
            pass # Fila vazia, normal

        # Reagenda a verificação se o processo ainda estiver rodando ou a janela existir
        if self.status_window and self.status_window.winfo_exists():
												 
             self.master.after(100, self.update_status_window) # Verifica a cada 100ms

    def append_to_status(self, text):
        """Adiciona texto ao widget de status."""
        if self.status_text_widget and self.status_text_widget.winfo_exists():
            self.status_text_widget.config(state='normal') # Habilita escrita
            self.status_text_widget.insert(tk.END, text)
            self.status_text_widget.see(tk.END) # Auto-scroll
            self.status_text_widget.config(state='disabled') # Desabilita escrita

    def read_process_output(self, process):
        """Lê a saída do processo em uma thread separada."""
        # Lê linha por linha da saída padrão do processo
        for line in iter(process.stdout.readline, ''):
            self.output_queue.put(line)
        process.stdout.close()
        self.output_queue.put(None) # Sinaliza o fim da saída

    def on_main_window_close(self):
        """Chamado ao fechar a janela principal."""
							  
        print(get_text(LOGS, "closing_main", current_language))
        if self.cripting_process:
																							  
            print(get_text(LOGS, "terminating_process", current_language))
            try:
                self.cripting_process.kill()
                self.cripting_process.wait(timeout=1)
																									   
                print(get_text(LOGS, "child_process_terminated", current_language))
            except Exception as e:
																								  
                print(get_text(LOGS, "child_process_error", current_language).format(e))
            finally:
                 self.cripting_process = None

        if self.status_window and self.status_window.winfo_exists():
            print(get_text(LOGS, "destroying_status", current_language))
												
            self.status_window.destroy()
            self.status_window = None
            self.status_text_widget = None

        print(get_text(LOGS, "destroying_main", current_language))
										  
        self.master.destroy()

        print(get_text(LOGS, "exiting_script", current_language))
										   
        #sys.exit(0)
        os._exit(0)

    def on_status_window_close(self):
        """Chamado ao fechar a janela de status."""
							  
        print(get_text(LOGS, "closing_status", current_language))
        if self.cripting_process:
																								   
            print(get_text(LOGS, "trying_terminate_process", current_language))
            try:
																							
                 print(get_text(LOGS, "sending_kill", current_language))
                 self.cripting_process.kill()
                 self.cripting_process.wait(timeout=3)
									   
                 print(get_text(UI, "process_killed", current_language))
            except subprocess.TimeoutExpired:
                 print(get_text(LOGS, "process_not_killed_timeout", current_language))
																																							  
            except Exception as e:
									   
                 print(get_text(LOGS, "error_killing_process", current_language).format(e))
            finally:
                 self.cripting_process = None
									   
                 print(get_text(LOGS, "process_ref_cleared", current_language))
                 try:
                     if self.status_window and self.status_window.winfo_exists() and \
                        self.status_text_widget and self.status_text_widget.winfo_exists():
											   
                         self.append_to_status("\n" + get_text(LOGS, "process_interrupted_by_user", current_language))
                 except tk.TclError:
										   
                     print(get_text(LOGS, "status_window_update_error", current_language))
        if self.status_window and self.status_window.winfo_exists():
																									
             print(get_text(LOGS, "destroying_status_window", current_language))
             self.status_window.destroy()
        self.status_window = None
        self.status_text_widget = None
							  
        print(get_text(LOGS, "status_window_closed", current_language))
        # self.master.destroy()


    def toggle_selection(self, path):
        """Adiciona ou remove um caminho da seleção."""
        widget_info = self.image_widgets.get(path)
        if not widget_info: return

        checkbutton = widget_info['checkbutton']
        if path in self.selected_paths:
            self.selected_paths.remove(path)
            checkbutton.deselect() # Atualiza visualmente o checkbutton
            widget_info['label'].config(relief=tk.FLAT, background='white') # Estilo não selecionado
        else:
            self.selected_paths.add(path)
            checkbutton.select() # Atualiza visualmente o checkbutton
            widget_info['label'].config(relief=tk.SOLID, background='lightblue') # Estilo selecionado

							  
        print("Selecteds:", [get_relative_path(p) for p in self.selected_paths]) # Debug


    def load_images(self, directory):
        """Carrega e exibe imagens do diretório especificado."""
        # Limpa ícones anteriores
        for widget in self.icon_frame.winfo_children():
            widget.destroy()
        self.image_widgets.clear()
        # Limpa seleções ao carregar novas imagens
        self.selected_paths.clear()
        # Define o diretório atual
        self.current_directory = directory

        image_files = get_image_files(directory)
        if not image_files:
             messagebox.showinfo(get_text(UI, "info_title", current_language), get_text(UI, "no_images_found", current_language).format(os.path.basename(directory))) # Linha 493
             return

        # Força a atualização da geometria para obter a largura correta do canvas
        self.master.update_idletasks()
        canvas_width = self.icon_canvas.winfo_width()

        # Se a largura ainda for muito pequena (janela acabou de abrir), use um valor padrão razoável
        if canvas_width <= 1:
            canvas_width = 550 # Ajuste este valor se necessário

        # Calcula colunas baseado na largura do CANVAS
        # Adiciona um pouco mais de padding no cálculo para garantir espaço
        item_width_estimate = ICON_SIZE[0] + 15 # Largura do ícone + padding (padx=5 de cada lado + 5 extra)
        cols = max(1, canvas_width // item_width_estimate)

        for i, img_path in enumerate(image_files):
            try:
                img = Image.open(img_path)
                img.thumbnail(ICON_SIZE)
                photo = ImageTk.PhotoImage(img)

                # Frame para agrupar imagem e checkbox
                item_frame = ttk.Frame(self.icon_frame, style='My.TFrame')

                # Usa Label para clique na imagem
                label = tk.Label(item_frame, image=photo, borderwidth=2, background='white')
                label.image = photo # Guarda referência
                label.pack()
                label.bind("<Button-1>", lambda e, p=img_path: self.toggle_selection(p))

                # Checkbutton - Inicia desmarcado pois limpamos selected_paths
                var = tk.IntVar(value=0)
                chk = ttk.Checkbutton(item_frame, variable=var, command=lambda p=img_path: self.toggle_selection(p))
                chk.pack()

                # Posiciona o frame do item na grade - A lógica de divmod já prioriza colunas
                row, col = divmod(i, cols)
                # Usar sticky='nw' para alinhar no canto superior esquerdo da célula da grade
                item_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nw')

                # Guarda referências
                self.image_widgets[img_path] = {'label': label, 'checkbutton': chk, 'var': var}

                # Não precisa mais verificar se já estava selecionado aqui
                # if img_path in self.selected_paths:
                #      label.config(relief=tk.SOLID, background='lightblue')

            except Exception as e:
                print(get_text(LOGS, "image_load_error", current_language).format(img_path, e))

        # Atualiza a configuração do scroll após adicionar todos os itens
        self.master.update_idletasks() # Garante que a geometria esteja atualizada
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))


    def select_all_visible(self):
        """Seleciona todas as imagens atualmente visíveis."""
        if not self.current_directory: # Verifica se um diretório foi carregado
            print(get_text(LOGS, "no_directory_loaded", current_language))
            return

        print(get_text(LOGS, "selecting_all_in", current_language).format(os.path.basename(self.current_directory))) # Debug
        # Pega todos os caminhos de imagem do diretório atual
        all_paths_in_current_dir = get_image_files(self.current_directory)

        for path in all_paths_in_current_dir:
            # Adiciona ao conjunto de seleção (se já não estiver)
            if path not in self.selected_paths:
                self.selected_paths.add(path)
            # Atualiza visualmente o widget correspondente (se ele existir)
            widget_info = self.image_widgets.get(path)
            if widget_info:
                # Correção: Usar a variável IntVar para marcar o checkbutton
                widget_info['var'].set(1) # Define o valor da variável para 1 (marcado)
                widget_info['label'].config(relief=tk.SOLID, background='lightblue')

        print("Selecteds:", [get_relative_path(p) for p in self.selected_paths]) # Debug

    def run_calibration(self):
        """Executa o script de calibração e fecha a janela principal."""
        try:
            # Prepara o comando para executar o script calibrationcript.py
            calibration_script = os.path.join(SCRIPT_DIR, 'calibrationcrypt.py')
            
            # Verifica se o arquivo existe
            if not os.path.exists(calibration_script):
                messagebox.showerror(get_text(UI, "error_title", current_language), get_text(UI, "calibration_script_not_found_msg", current_language).format(calibration_script))
                return
                
            # Executa o script em um novo processo
            subprocess.Popen(
                [sys.executable, calibration_script],
                cwd=SCRIPT_DIR
            )
            
            # Fecha a janela principal
            print(get_text(LOGS, "closing_main_for_calibration", current_language))
            self.master.destroy()
            
        except Exception as e:
            messagebox.showerror(get_text(UI, "error_title", current_language), 
                               get_text(UI, "calibration_script_error", current_language).format(e))
																									
    def run_script(self):
        """Salva a config, ativa a janela do jogo, executa crypting.py e mostra a saída."""
        if self.cripting_process:
             messagebox.showwarning(get_text(UI, "warning_title", current_language),get_text(UI, "script_already_running", current_language))
																						   
             return
        if not self.selected_paths:
            messagebox.showwarning(get_text(UI, "warning_title", current_language), 
                                 get_text(UI, "no_images_selected", current_language))
																					  
            return
            
        # Verifica se o campo de quantidade está preenchido
        how_many_value = self.how_many_cripts_var.get().strip()
        if not how_many_value:
            messagebox.showwarning(get_text(UI, "warning_title", current_language), 
                      get_text(UI, "enter_crypt_quantity", current_language))
																			 
            return
            
        # Salva a configuração
        try:
            config = configparser.ConfigParser()
            # Verifica se o arquivo existe e carrega se existir
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
            
            # Garante que a seção Settings existe
            if 'Settings' not in config:
                config['Settings'] = {}
                
            # Atualiza o valor de how_many_cripts
            config['COORDINATES']['how_many_cripts'] = how_many_value
            
            # Salva as imagens selecionadas
            config['Settings']['selected_images'] = ','.join([get_relative_path(p) for p in self.selected_paths]) # Linha 434
            
            # Escreve no arquivo
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
                
            print(f"Configuração salva. Quantidade de criptas: {how_many_value}")
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")
            messagebox.showerror(get_text(UI, "error_title", current_language), 
                                get_text(UI, "save_config_fail", current_language).format(e))
																							 
            return

        # --- ATIVAR JANELA DO JOGO ---
        game_window_title = 'Total Battle' # <-- CONFIRME ESTE TÍTULO!
        print(get_text(LOGS, "trying_activate_window", current_language).format(game_window_title))
        # The call below should now work as the function is defined
        if not activate_window_by_title(game_window_title):
            messagebox.showwarning(get_text(UI, "warning_title", current_language), 
                      get_text(UI, "game_window_not_found", current_language).format(game_window_title))
																										
            # Decide se quer continuar mesmo assim ou parar
            exit()
            #return # Descomente para parar se a janela não for ativada

        # --- Continua com a lógica existente ---
        # Formata os caminhos relativos para o config
        relative_paths = [get_relative_path(p) for p in self.selected_paths]
        config_value = str(relative_paths) # Converte a lista para string '[path1, path2]'

        print(f"Salvando no config: search_cript = {config_value}") # Debug

        # Atualiza o arquivo de configuração
        config = configparser.ConfigParser()
        config.optionxform = str
        try:
            if not os.path.exists(CONFIG_FILE):
                 messagebox.showerror(get_text(UI, "error_title", current_language),
                                     get_text(UI, "config_file_not_found", current_language).format(CONFIG_FILE))
																																																																	   
                 return

            config.read(CONFIG_FILE)

            if 'COORDINATES' not in config:
                messagebox.showerror(get_text(UI, "error_title", current_language),
                                     get_text(UI, "coordinates_section_not_found", current_language))
																																												  
                return

            config['COORDINATES']['search_cript'] = config_value

            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
								  

            # Cria a janela de status ANTES de iniciar o processo
            self.create_status_window()
            self.append_to_status(get_text(LOGS, "starting_script", current_language)) # Mensagem inicial
						  

            # Executa o script crypting.py capturando a saída
            self.cripting_process = subprocess.Popen(
                [sys.executable, TEST_SCRIPT],
                cwd=SCRIPT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Captura erros também
                text=True, # Decodifica a saída como texto
                bufsize=1, # Line-buffered
                universal_newlines=True # Garante newlines consistentes
            )

            # Inicia a thread para ler a saída do processo
            self.output_reader_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.cripting_process,),
                daemon=True # Permite que a aplicação feche mesmo se a thread estiver rodando
            )
            self.output_reader_thread.start()

            # Inicia a atualização da janela de status
            self.update_status_window()
									  
																						  

            # Esconde a janela principal (opcional)
            self.master.withdraw()
												  
								   
										   
																	 
															   
											  
																		   
				 

            # NÃO FECHA MAIS A JANELA PRINCIPAL AQUI
            # self.master.quit()
													
												  
																								   
				 
												 

															
										   

													   
									  

														 
									

        except configparser.Error as e:
             messagebox.showerror(get_text(UI, "config_error_title", current_language),
                                get_text(UI, "config_read_write_error", current_language).format(e))
																									
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro inesperado:\n{e}")




# --- Execução Principal ---
if __name__ == "__main__":
    current_language = get_current_language()
    # Verifica se os diretórios de imagem existem
    if not os.path.isdir(COMMON_DIR):
        print(f"Criando diretório ausente: {COMMON_DIR}")
        os.makedirs(COMMON_DIR, exist_ok=True)
    if not os.path.isdir(EPIC_DIR):
        print(f"Criando diretório ausente: {EPIC_DIR}")
        os.makedirs(EPIC_DIR, exist_ok=True)

    root = tk.Tk()
    app = ImageSelectorApp(root)
    root.mainloop()
    