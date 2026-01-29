"""
PyAutoGUI ve Ekran Parlaklığı Kontrolü kullanarak sistem genelinde kontrol sağlar.

Bu modül, el hareketlerinden gelen komutları (örn: "Ses Aç", "Tıkla") 
işletim sistemi seviyesinde aksiyonlara dönüştürür.

Özellik Seti (Feature Set):
1. Mouse Kontrolü (Hareket, Tıklama, Scroll)
2. Ses Kontrolü (Ses Aç/Kıs/Mute)
3. Medya Kontrolü (Oynat/Durdur, Sonraki/Önceki, İleri/Geri Sarma)
4. Ekran Parlaklığı (SBC kütüphanesi ile)
5. Zoom Kontrolü (Ctrl + Scroll)
6. Ekran Görüntüsü (Screenshot)
"""

import pyautogui
import screen_brightness_control as sbc
import time
import math

# PyAutoGUI Fail-Safe off 
# (Fare köşeye gidince programın çökmesini engeller, el hareketleri için gereklidir)
pyautogui.FAILSAFE = False

class SystemController:
    def __init__(self):
        # Ekran boyutlarını al (Mouse mapping için)
        self.screen_w, self.screen_h = pyautogui.size()
        
        # --- ZAMANLAMA / COOLDOWNS ---
        # Her aksiyonun son yapılma zamanını tutar.
        # Bu sayede el hareketi algılandığında saniyede 100 kere tuşa basılmasını engelleriz.
        self.last_action_time = {
            'click': 0,
            'scroll': 0,
            'zoom': 0,
            'volume': 0,
            'brightness': 0,
            'media': 0,
            'seek': 0
        }
        
        # Cooldown values (Saniye cinsinden bekleme süreleri)
        self.cd_very_fast = 0.05 # Mouse, Ses, Parlaklık için (Akıcı olması lazım)
        self.cd_fast = 0.15      # Scroll, Zoom için
        self.cd_medium = 0.5     # Şarkı geçişleri için
        self.cd_long = 1.0       # Play/Pause, Mute gibi on/off işlemleri için (Toggle)

    # --- MOUSE HAREKETLERİ ---
    def move_mouse(self, x_cam, y_cam, w_cam, h_cam):
        """
        Kamera koordinatlarını ekran koordinatlarına çevirir ve mouse'u hareket ettirir.
        Kameradaki (x,y) noktası ekrandaki (target_x, target_y) noktasına orantılanır.
        
        Kenarlara ulaşmayı kolaylaştırmak için 'frame_reduction' kullanılır.
        """
        # İnterpolasyon (Kenarlara daha rahat ulaşmak için algılama çerçevesini daraltıyoruz)
        frame_reduction = 100 
        
        x = x_cam
        y = y_cam
        
        # Koordinat dönüşümü (Mapping)
        # Matematiksel Oranlama: (Gelen Değer - Min) / (Max - Min)
        x_eff = (x - frame_reduction) / (w_cam - 2 * frame_reduction)
        y_eff = (y - frame_reduction) / (h_cam - 2 * frame_reduction)
        
        # Sınırla (Clamp) 0.0 - 1.0 arasına hapset
        x_eff = max(0, min(1, x_eff))
        y_eff = max(0, min(1, y_eff))
        
        # Ekran boyutuna genişlet
        target_x = self.screen_w * x_eff
        target_y = self.screen_h * y_eff
        
        # PyAutoGUI ile imleci taşı
        pyautogui.moveTo(target_x, target_y)

    def left_click(self):
        """Sol Tıklama yapar. Çift tıklamayı önlemek için cooldown 0.3sn vardır."""
        current_time = time.time()
        if current_time - self.last_action_time['click'] > 0.3:
            pyautogui.click()
            self.last_action_time['click'] = current_time
            return True
        return False

    # --- ZOOM & SCROLL (3 PARMAK - SAĞ EL) ---
    def scroll(self, dy):
        """
        Dikey Scroll (Tekerlek) işlemi.
        dy: Elin dikeydeki değişim miktarı. 
        dy < 0 -> Yukarı hareket -> Sayfayı YUKARI kaydır
        dy > 0 -> Aşağı hareket -> Sayfayı AŞAĞI kaydır
        """
        current_time = time.time()
        if current_time - self.last_action_time['scroll'] < self.cd_fast:
            return None
            
        threshold = 20 # Hassasiyet eşiği
        if dy < -threshold:
            pyautogui.scroll(120) # Scroll Up (Pozitif değer = Yukarı)
            self.last_action_time['scroll'] = current_time
            return "SCROLL UP"
        elif dy > threshold:
            pyautogui.scroll(-120) # Scroll Down (Negatif değer = Aşağı)
            self.last_action_time['scroll'] = current_time
            return "SCROLL DOWN"
        return None

    def zoom(self, dx):
        """
        Zoom İşlemi (Ctrl + Scroll).
        dx: Elin yataydaki değişim miktarı.
        dx > 0 -> Sağ -> Zoom In (Büyüt)
        dx < 0 -> Sol -> Zoom Out (Küçült)
        """
        current_time = time.time()
        if current_time - self.last_action_time['zoom'] < self.cd_fast:
            return None
            
        threshold = 20
        if dx > threshold: # Sağ Hareket -> Zoom In
            with pyautogui.hold('ctrl'): # Ctrl tuşunu basılı tutarken scroll yap
                pyautogui.scroll(100)
            self.last_action_time['zoom'] = current_time
            return "ZOOM IN"
        elif dx < -threshold: # Sol Hareket -> Zoom Out
            with pyautogui.hold('ctrl'):
                pyautogui.scroll(-100)
            self.last_action_time['zoom'] = current_time
            return "ZOOM OUT"
        return None

    # --- SES & PARLAKLIK (4 PARMAK - SAĞ EL) ---
    def change_volume(self, dy):
        """
        Sistem Sesini değiştirir.
        Yukarı Hareket -> Ses Aç
        Aşağı Hareket -> Ses Kıs
        """
        current_time = time.time()
        if current_time - self.last_action_time['volume'] < self.cd_very_fast:
            return None
            
        threshold = 15
        if dy < -threshold: # Yukarı -> Ses Aç
            pyautogui.press('volumeup')
            self.last_action_time['volume'] = current_time
            return "SES ++"
        elif dy > threshold: # Aşağı -> Ses Kıs
            pyautogui.press('volumedown')
            self.last_action_time['volume'] = current_time
            return "SES --"
        return None

    def change_brightness(self, dx):
        """
        Ekran Parlaklığını değiştirir. 
        Sağ Hareket -> Parlaklık Artır
        Sol Hareket -> Parlaklık Azalt
        """
        current_time = time.time()
        if current_time - self.last_action_time['brightness'] < self.cd_very_fast:
            return None
            
        threshold = 15
        change_amount = 5 # Her adımda %5 değişim
        
        try:
            # Mevcut parlaklığı al
            current_ug = sbc.get_brightness()
            if not current_ug: return None
            val = current_ug[0]
            
            if dx > threshold: # Sağ -> Parlaklık Artır
                new_val = min(100, val + change_amount)
                sbc.set_brightness(new_val)
                self.last_action_time['brightness'] = current_time
                return f"PARLAKLIK {new_val}%"
                
            elif dx < -threshold: # Sol -> Parlaklık Azalt
                new_val = max(0, val - change_amount)
                sbc.set_brightness(new_val)
                self.last_action_time['brightness'] = current_time
                return f"PARLAKLIK {new_val}%"
        except:
            return "HATA: SBC"
            
        return None

    def toggle_mute(self):
        """Sesi tamamen kapatır/açar (Mute). 1 saniyede bir çalışır."""
        current_time = time.time()
        if current_time - self.last_action_time['volume'] < self.cd_long:
            return False
            
        pyautogui.press('volumemute')
        self.last_action_time['volume'] = current_time 
        return True

    # --- MEDYA (4 PARMAK - SOL EL V19) ---
    def media_control_track(self, dy):
        """
        Müzik/Video parça geçişi.
        Yukarı -> Önceki Parça
        Aşağı -> Sonraki Parça
        """
        current_time = time.time()
        if current_time - self.last_action_time['media'] < self.cd_medium:
            return None
            
        threshold = 30
        if dy < -threshold: # Yukarı -> Önceki
            pyautogui.press('prevtrack')
            self.last_action_time['media'] = current_time
            return "ONCEKI PARCA"
        elif dy > threshold: # Aşağı -> Sonraki
            pyautogui.press('nexttrack')
            self.last_action_time['media'] = current_time
            return "SONRAKI PARCA"
        return None

    def media_control_seek(self, dx):
        """
        İleri/Geri Sarma. (Youtube gibi uygulamalar için ok tuşları kullanılır)
        Sağ -> İleri Sar
        Sol -> Geri Sar
        """
        current_time = time.time()
        if current_time - self.last_action_time['seek'] < self.cd_fast:
            return None
            
        threshold = 30
        if dx > threshold: # Sağ -> İleri
            pyautogui.press('right')
            self.last_action_time['seek'] = current_time
            return "ILERI SAR >>"
        elif dx < -threshold: # Sol -> Geri
            pyautogui.press('left')
            self.last_action_time['seek'] = current_time
            return "<< GERI SAR"
        return None

    def take_screenshot(self):
        """Ekran Görüntüsü alır (Win+Shift+S kısayolu gönderir)"""
        current_time = time.time()
        # Ekran görüntüsü sık sık alınmamalı, uzun cooldown olmalı.
        if current_time - self.last_action_time['media'] < 2.0: 
            return False
            
        pyautogui.hotkey('win', 'shift', 's')
        self.last_action_time['media'] = current_time # Media cooldown'u ortak kullanalım ki çakışmasın
        return True

    def toggle_play_pause(self):
        """Müzik/Video oynat ve durdur."""
        current_time = time.time()
        if current_time - self.last_action_time['media'] < self.cd_long:
            return False
            
        pyautogui.press('playpause')
        self.last_action_time['media'] = current_time
        return True


