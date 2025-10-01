import dearpygui.dearpygui as dpg
import cv2
import numpy as np
import time
from ultralytics import YOLO
import math
import win32api
import win32con
from pynput import keyboard
import threading

class AimAssist:
    def __init__(self):
        # Carrega o modelo YOLO
        self.model = YOLO('yolov8n.pt')
        
        # Configurações da tela
        self.screen_width = win32api.GetSystemMetrics(0)
        self.screen_height = win32api.GetSystemMetrics(1)
        self.screen_center = (self.screen_width // 2, self.screen_height // 2)
        
        # CONFIGURAÇÃO DE VELOCIDADE MÁXIMA
        self.smooth_factor = 1.5
        self.activation_distance = 1000
        self.head_offset_percentage = 0.12
        
        # Otimizações de performance
        self.processing_delay = 0.001
        
        # Estado do aim assist
        self.enabled = False
        self.running = False
        self.thread = None
        self.person_class = 0
        
        # Status para a GUI
        self.status_text = "Desligado"
        self.target_count = 0
        
        print("Aimbot Iniciado!")

    def calculate_head_position(self, x1, y1, x2, y2):
        """Calcula a posição da cabeça baseada na bounding box"""
        bbox_height = y2 - y1
        head_region_height = bbox_height * self.head_offset_percentage
        center_x = (x1 + x2) / 2
        head_y = y1 + (head_region_height * 0.6)
        return (int(center_x), int(head_y))

    def exponential_smooth_move(self, current_pos, target_pos, factor):
        """Movimento suave em direção ao alvo"""
        dx = target_pos[0] - current_pos[0]
        dy = target_pos[1] - current_pos[1]
        move_x = dx * factor
        move_y = dy * factor
        return int(move_x), int(move_y)

    def move_mouse(self, dx, dy):
        """Move o mouse usando win32api"""
        if dx != 0 or dy != 0:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)

    def get_closest_enemy_head(self, frame):
        """Encontra a cabeça mais próxima do centro"""
        try:
            # Reduz resolução para processamento mais rápido
            small_frame = cv2.resize(frame, (640, 480))
            
            # Inference com YOLO
            results = self.model(small_frame, verbose=False, imgsz=640, conf=0.5)
            
            closest_distance = float('inf')
            head_position = None
            target_count = 0
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        if int(box.cls) == self.person_class:
                            target_count += 1
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            
                            # Escala de volta para coordenadas da tela
                            scale_x = self.screen_width / 640
                            scale_y = self.screen_height / 480
                            x1, x2 = x1 * scale_x, x2 * scale_x
                            y1, y2 = y1 * scale_y, y2 * scale_y
                            
                            head_x, head_y = self.calculate_head_position(x1, y1, x2, y2)
                            
                            distance = math.sqrt(
                                (head_x - self.screen_center[0]) ** 2 + 
                                (head_y - self.screen_center[1]) ** 2
                            )
                            
                            if distance < closest_distance and distance < self.activation_distance:
                                closest_distance = distance
                                head_position = (head_x, head_y)
            
            self.target_count = target_count
            return head_position
            
        except Exception as e:
            print(f"Erro na detecção: {e}")
            return None

    def capture_screen(self):
        """Captura a tela inteira"""
        import win32gui
        import win32ui
        import win32con
        
        try:
            hdesktop = win32gui.GetDesktopWindow()
            width = self.screen_width
            height = self.screen_height
            
            desktop_dc = win32gui.GetWindowDC(hdesktop)
            img_dc = win32ui.CreateDCFromHandle(desktop_dc)
            mem_dc = img_dc.CreateCompatibleDC()
            
            screenshot = win32ui.CreateBitmap()
            screenshot.CreateCompatibleBitmap(img_dc, width, height)
            mem_dc.SelectObject(screenshot)
            mem_dc.BitBlt((0, 0), (width, height), img_dc, (0, 0), win32con.SRCCOPY)
            
            bmpinfo = screenshot.GetInfo()
            bmpstr = screenshot.GetBitmapBits(True)
            
            img = np.frombuffer(bmpstr, dtype='uint8')
            img.shape = (height, width, 4)
            
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Cleanup
            mem_dc.DeleteDC()
            win32gui.DeleteObject(screenshot.GetHandle())
            win32gui.ReleaseDC(hdesktop, desktop_dc)
            
            return img
            
        except Exception as e:
            print(f"Erro na captura de tela: {e}")
            return None

    def aimbot_loop(self):
        """Loop principal do aimbot rodando em thread separada"""
        print("Thread do aimbot iniciada")
        
        while self.running:
            if self.enabled:
                try:
                    # Atualiza status
                    self.status_text = "Procurando alvos..."
                    
                    # Captura e processa
                    frame = self.capture_screen()
                    if frame is not None:
                        head_position = self.get_closest_enemy_head(frame)
                        
                        if head_position:
                            self.status_text = f"Alvo detectado! ({self.target_count} alvos)"
                            current_x, current_y = win32api.GetCursorPos()
                            move_x, move_y = self.exponential_smooth_move(
                                (current_x, current_y), 
                                head_position, 
                                self.smooth_factor
                            )
                            self.move_mouse(move_x, move_y)
                        else:
                            self.status_text = f"Sem alvos ({self.target_count} detectados)"
                    
                except Exception as e:
                    self.status_text = f"Erro: {str(e)[:20]}..."
                    print(f"Erro no loop: {e}")
                
                time.sleep(self.processing_delay)
            else:
                self.status_text = "Desligado"
                time.sleep(0.1)  # Espera quando desligado

    def toggle_aimbot(self):
        """Alterna o estado do aimbot"""
        self.enabled = not self.enabled
        
        if self.enabled and not self.running:
            # Inicia a thread se não estiver rodando
            self.running = True
            self.thread = threading.Thread(target=self.aimbot_loop, daemon=True)
            self.thread.start()
            print("Aimbot thread iniciada")
        
        return self.enabled

    def stop_aimbot(self):
        """Para completamente o aimbot"""
        self.running = False
        self.enabled = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        print("Aimbot completamente parado")

# Criar instância global do AimAssist
aim_assist = AimAssist()

dpg.create_context()

# Callbacks atualizados
def aimbot_button_clicked(sender, app_data):
    if aim_assist.toggle_aimbot():
        dpg.set_item_label(sender, "Parar Aimbot")
        dpg.set_value("status_text", "Status: LIGADO - Procurando alvos...")
        print("Aimbot ATIVADO")
    else:
        dpg.set_item_label(sender, "Ativar Aimbot")
        dpg.set_value("status_text", "Status: DESLIGADO")
        print("Aimbot DESATIVADO")

def sensitivity_changed(sender, app_data):
    aim_assist.smooth_factor = app_data
    dpg.set_value("sensitivity_value", f"Sensibilidade: {app_data:.1f}")

def range_changed(sender, app_data):
    aim_assist.activation_distance = app_data
    dpg.set_value("range_value", f"Alcance: {app_data}px")

def update_status():
    """Atualiza o status na GUI periodicamente"""
    if aim_assist.enabled:
        status_color = [0, 255, 0, 255]  # Verde
        status = aim_assist.status_text
    else:
        status_color = [255, 0, 0, 255]  # Vermelho
        status = "DESLIGADO"
    
    dpg.set_value("status_text", f"Status: {status}")
    dpg.configure_item("status_text", color=status_color)

# Criar tema roxo
with dpg.theme() as tema_roxo:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_Button, [128, 0, 128, 255])
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [160, 32, 240, 255])
        dpg.add_theme_color(dpg.mvThemeCol_Tab, [128, 0, 128, 255])
        dpg.add_theme_color(dpg.mvThemeCol_TabActive, [160, 32, 240, 255])
        dpg.add_theme_color(dpg.mvThemeCol_TabHovered, [186, 85, 211, 255])

def main():
    with dpg.window(label="Core Cheats", 
        width=540, 
        height=400, 
        no_title_bar=True,
        no_move=True,
        no_resize=True,
        no_collapse=True,
        no_close=True) as main_window:

        dpg.bind_item_theme(main_window, tema_roxo)

        with dpg.tab_bar():
            with dpg.tab(label="Aimbot"):
                dpg.add_text("Configurações do Aimbot")
                dpg.add_spacer(height=10)
                
                # Botão principal
                dpg.add_button(label="Ativar Aimbot", 
                              callback=aimbot_button_clicked,
                              width=200, height=30)
                
                dpg.add_spacer(height=20)
                
                # Configurações
                dpg.add_text("Configurações Avançadas:")
                
                # Sensibilidade
                dpg.add_text("Sensibilidade:")
                dpg.add_slider_float(label="", 
                                    default_value=aim_assist.smooth_factor,
                                    min_value=0.1, 
                                    max_value=3.0,
                                    callback=sensitivity_changed)
                dpg.add_text(f"Sensibilidade: {aim_assist.smooth_factor:.1f}", tag="sensitivity_value")
                
                # Alcance
                dpg.add_text("Alcance de Detecção:")
                dpg.add_slider_int(label="", 
                                  default_value=aim_assist.activation_distance,
                                  min_value=100, 
                                  max_value=2000,
                                  callback=range_changed)
                dpg.add_text(f"Alcance: {aim_assist.activation_distance}px", tag="range_value")
                
                dpg.add_spacer(height=10)
                
                # Status dinâmico
                dpg.add_text("Tecla F2: Ligar/Desligar Rapidamente", color=[255, 255, 0, 255])
                dpg.add_text("Status: DESLIGADO", tag="status_text", color=[255, 0, 0, 255])

    # Configurar viewport
    dpg.create_viewport(title="Core Cheats", width=540, height=400)
    dpg.set_viewport_clear_color([19, 19, 19, 255])

    # Setup e loop principal
    dpg.setup_dearpygui()
    dpg.show_viewport()

    # Loop principal com atualização de status
    while dpg.is_dearpygui_running():
        update_status()
        dpg.render_dearpygui_frame()

    # Limpeza ao fechar
    aim_assist.stop_aimbot()
    dpg.destroy_context()

if __name__ == "__main__":
    main()