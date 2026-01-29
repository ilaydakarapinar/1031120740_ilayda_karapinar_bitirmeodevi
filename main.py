"""
Başparmak YOK - 4 Parmak Sistemi (Sağ ve Sol El Ayrımı Mevcut)

Bu ana dosya (main.py):
1. Kamerayı açar ve görüntü alır.
2. HandDetector ile elleri ve parmakları bulur.
3. Elin Sağ mı Sol mu olduğuna karar verir.
4. Parmak sayısına göre (Mod Tabanlı) ilgili Sistem Kontrol komutunu çağırır.
5. Ekran üzerine bilgi ve geri bildirim çizer.

MODLAR (Sağ El):
- 1 Parmak: Mouse Hareket
- 2 Parmak: Tıklama (Geçişte) / Scroll+Zoom (Hareketliyse)
- 3 Parmak: Ekran Görüntüsü (Yukarı Hareket)
- 4 Parmak: Ses (Dikey) / Parlaklık (Yatay)

MODLAR (Sol El V19):
- 1 Parmak: Mute (Sessiz) - Göster/Çek
- 2 Parmak: Play/Pause - Göster/Çek
- 4 Parmak: Medya Navigasyon (Şarkı Değiş/Sar)
"""

import cv2
import time
import numpy as np
from hand_detector import HandDetector
from controller import SystemController

def count_active_fingers(fingers):
    """
    Aktif parmak sayısını hesaplar.
    fingers[0] = Başparmak (Bu sistemde YOKSAYILIR)
    fingers[1...4] = İşaret, Orta, Yüzük, Serçe (Toplanır)
    """
    return sum(fingers[1:])

def main():
    # Kamerayı Başlat (Index 0 genellikle varsayılan webcam'dir)
    cap = cv2.VideoCapture(0)
    
    # Çözünürlük Ayarları (1280x720 olarak kullanıcı tarafından ayarlandı)
    w_cam, h_cam = 680, 480
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w_cam)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h_cam)
    
    if not cap.isOpened():
        print("HATA: Kamera acilamadi!")
        return
        
    # Dedektör ve Kontrolcüyü Başlat
    detector = HandDetector(max_hands=1, detection_confidence=0.7, tracking_confidence=0.7)
    
    try:
        sys_ctrl = SystemController()
    except Exception as e:
        print(f"Controller başlatma hatası: {e}")
        return

    # Mouse Yumuşatma (Smoothing) Değişkenleri
    # Mouse'un titrememesi için önceki pozisyon ile şimdiki pozisyon arasında ortalama alınır.
    p_loc_x, p_loc_y = 0, 0
    c_loc_x, c_loc_y = 0, 0
    smoothing = 5 # Ne kadar yüksekse o kadar yumuşak (ama gecikmeli) olur
    
    # Hareket Takibi için değişkenler (Önceki avuç içi pozisyonu)
    last_palm_x, last_palm_y = 0, 0
    
    # Durum Takibi
    prev_finger_count = 0
    action_text = ""
    action_time = 0
    
    # Sabitlik/Kilit Kontrolü (Sol el komutlarını bir kez tetiklemek için)
    static_start_time = 0
    is_static_gesture_active = False # Hareket yapıldıysa kilitlenir
    STATIC_THRESHOLD_SEC = 1.0     
    MOVEMENT_THRESHOLD = 5         
    
    print("="*60)
    print("")
    print("="*60)

    while True:
        try:
            # Kameradan bir kare oku
            success, img = cap.read()
            if not success: break
            
            # Görüntüyü Yatay Çevir (Ayna Etkisi - Mirror)
            # Bu işlemden sonra Sağ el ekranda Sağda görünür.
            img = cv2.flip(img, 1)
            
            # El Algılama
            img = detector.find_hands(img, draw=True)
            landmarks = detector.find_positions(img)
            current_time = time.time()
            
            if landmarks:
                # 1. El Türü (Sağ/Sol) Tespiti
                # hand_detector içindeki düzeltme ile doğru etiketi alırız.
                hand_type = detector.get_handedness(0) # İlk el
                
                # Parmakları Say
                fingers = detector.fingers_up(landmarks)
                finger_count = count_active_fingers(fingers)
                
                # Ekrana Bilgi Yazdır (Hangi El ve Kaç Parmak)
                color_hand = (255, 0, 0) if hand_type == "Left" else (0, 0, 255) # Sol: Mavi, Sağ: Kırmızı
                cv2.putText(img, f"El: {hand_type}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_hand, 2)
                cv2.putText(img, f"Parmak: {finger_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

                # 2. Avuç İçi Pozisyonu (Landmark 9) ve Hareket Değişimi (Delta)
                palm_x, palm_y = landmarks[9][1], landmarks[9][2]
                dx = palm_x - last_palm_x # Yatay değişim
                dy = palm_y - last_palm_y # Dikey değişim
                
                # ==========================================================
                # SAĞ EL MANTIĞI (MOUSE & AYARLAR)
                # ==========================================================
                if hand_type == "Right" or hand_type is None:
                    try:
                        # Mod 1: MOUSE (1 Parmak - Sadece İşaret)
                        if finger_count == 1 and fingers[1] == 1:
                            # İşaret parmağı ucu (Landmark 8)
                            x1, y1 = landmarks[8][1], landmarks[8][2]
                            
                            # Yumuşatma Hesabı
                            c_loc_x = p_loc_x + (x1 - p_loc_x) / smoothing
                            c_loc_y = p_loc_y + (y1 - p_loc_y) / smoothing
                            
                            # Mouse Taşıma Komutu
                            sys_ctrl.move_mouse(c_loc_x, c_loc_y, w_cam, h_cam)
                            p_loc_x, p_loc_y = c_loc_x, c_loc_y
                            
                            cv2.circle(img, (x1, y1), 10, (255, 0, 255), cv2.FILLED)
                            action_text = "MOUSE"
                            action_time = current_time 
                        
                        # Mod 2: TIKLAMA (Geçiş Kontrolü)
                        # Parmak sayısı 1'den 2'ye geçerse (Orta parmak kalkarsa) TIKLA
                        if finger_count == 2 and prev_finger_count == 1:
                             if sys_ctrl.left_click():
                                 cv2.putText(img, "TIKLA!", (palm_x, palm_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                        # Mod 2 HAREKET: Scroll (Dikey) / Zoom (Yatay)
                        if finger_count == 2:
                            res = None
                            if abs(dy) > abs(dx): res = sys_ctrl.scroll(dy) # Dikey hareket baskınsa SCROLL
                            else: res = sys_ctrl.zoom(dx) # Yatay hareket baskınsa ZOOM
                            if res: action_text = res; action_time = current_time

                        # Mod 3 HAREKET: Ekran Görüntüsü (Sadece yukarı çek) 
                        if finger_count == 3:
                            if dy < -30: # Hızlıca yukarı
                                if sys_ctrl.take_screenshot():
                                    action_text = "EKRAN GORUNTUSU"
                                    action_time = current_time

                        # Mod 4 HAREKET: Ses (Dikey) / Parlaklık (Yatay)
                        if finger_count == 4:
                            res = None
                            if abs(dy) > abs(dx): res = sys_ctrl.change_volume(dy)
                            else: res = sys_ctrl.change_brightness(dx)
                            if res: action_text = res; action_time = current_time

                    except Exception as e:
                        # Sağ el hatası olursa programı durdurma, log bas
                        print(f"Sag El Hatasi: {e}")

                # ==========================================================
                # SOL EL MANTIĞI (MEDYA & KOMUTLAR)
                # ==========================================================
                elif hand_type == "Left":
                    try:
                        # TRIGGER / LOCK MANTIGI
                        # Hareket bir kez algılanır ve 'is_static_gesture_active' True yapılır.
                        # El kapanana kadar (finger_count == 0) tekrar tetiklenmez.
                        
                        # Mod: MUTE (1 Parmak) -> Aç/Kapa
                        if finger_count == 1:
                            if not is_static_gesture_active: # Kilitli değilse yap
                                if sys_ctrl.toggle_mute():
                                    action_text = "SESSIZ / SESLI"
                                    action_time = current_time
                                    is_static_gesture_active = True # Kilitle
                        
                        # Mod: PLAY/PAUSE (2 Parmak) -> Oynat/Durdur
                        elif finger_count == 2:
                            if not is_static_gesture_active: 
                                if sys_ctrl.toggle_play_pause():
                                    action_text = "OYNAT / DURDUR"
                                    action_time = current_time
                                    is_static_gesture_active = True 
                        
                        # Mod: MEDYA NAVİGASYON (4 Parmak - Hareketli)
                        # Bu sürekli bir hareket olduğu için kilit mekanizması kullanılmaz.
                        elif finger_count == 4:
                            res = None
                            if abs(dy) > abs(dx): res = sys_ctrl.media_control_track(dy) # Dikey: Şarkı
                            else: res = sys_ctrl.media_control_seek(dx) # Yatay: Sarma
                            if res: action_text = res; action_time = current_time
                            
                        # RESET: El Kapandıysa (0 Parmak) Kilidi Aç
                        elif finger_count == 0:
                            is_static_gesture_active = False

                    except Exception as e:
                        print(f"Sol El Hatasi: {e}")

                # Güncelle
                last_palm_x, last_palm_y = palm_x, palm_y
                prev_finger_count = finger_count
                
                # Parmak sayısını ekrana daimi yaz
                # (Zaten yukarıda yazıldı ama debug için burada kalabilir veya çıkarılabilir)
                # cv2.putText(img, f"Parmak: {finger_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            else:
                prev_finger_count = 0
            
            # Aksiyon Mesajını Göster (Eğer süre dolmadıysa)
            if (current_time - action_time) < 1.0:
                text_size = cv2.getTextSize(action_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 3)[0]
                text_x = (w_cam - text_size[0]) // 2
                cv2.rectangle(img, (text_x - 10, 120), (text_x + text_size[0] + 10, 155), (0, 0, 0), cv2.FILLED)
                cv2.putText(img, action_text, (text_x, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

            # Görüntüyü Göster
            cv2.imshow("bitirme odevi", img)
            
            # Çıkış (Q Tuşu)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        except Exception as e:
            # Ana döngüdeki kritik hataları yakala
            print(f"Ana Döngü Hatası: {e}")
            time.sleep(0.1) # CPU'yu boğmamak için bekle
            
    # Temizlik
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

