"""
Hand Detector Module (El Algılama Modülü)
MediaPipe Tasks API kullanarak el algılama ve landmark (eklem noktası) çıkarma işlemlerini yapar.

Bu modül, kamera görüntüsünden elleri tespit eder, parmak eklemlerinin koordinatlarını çıkarır
ve bu koordinatları diğer modüllerin kullanımı için sunar. Ayrıca titremeyi azaltmak için
basit bir yumuşatma (smoothing) uygular.
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import os
from collections import deque


class HandDetector:
    """
    El algılama ve parmak pozisyonlarını tespit eden sınıf.
    MediaPipe kütüphanesini kullanır.
    """

    def __init__(self, max_hands=1, detection_confidence=0.5, tracking_confidence=0.5):
        """
        Sınıfın başlatıcı metodu. Gerekli ayarları yapar ve modeli yükler.

        Args:
            max_hands (int): Aynı anda algılanacak maksimum el sayısı. Varsayılan: 1.
            detection_confidence (float): El algılama güven eşiği (0.0 - 1.0). Düşükse daha çok hata yapabilir.
            tracking_confidence (float): El takibi güven eşiği.
        """
        self.max_hands = max_hands
        
        # Model dosyasının tam yolunu bul
        # hand_landmarker.task dosyası bu script ile aynı klasörde olmalı
        model_path = os.path.join(os.path.dirname(__file__), 'hand_landmarker.task')
        
        # HandLandmarker seçeneklerini ayarla (Konfigürasyon)
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE, # Resim modu (Video akışı olsa da kare kare işleriz)
            num_hands=max_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=tracking_confidence
        )
        
        # Dedektörü oluştur (Modeli yükle)
        try:
            self.detector = vision.HandLandmarker.create_from_options(options)
            print("Model başarıyla yüklendi.")
        except Exception as e:
            print(f"Model yüklenirken hata oluştu: {e}")
            raise
        
        # Parmak ucu landmark indeksleri (Sabit değerler)
        # 4: Başparmak, 8: İşaret, 12: Orta, 16: Yüzük, 20: Serçe
        self.tip_ids = [4, 8, 12, 16, 20]
        
        # Son algılama sonucu (Her karede güncellenir)
        self.results = None
        
        # Yumuşatma (smoothing) için geçmiş veriler
        self.landmark_history = deque(maxlen=5)

    def find_hands(self, img, draw=True):
        """
        Görüntüdeki elleri algılar ve opsiyonel olarak çizer.
        Bu fonksiyon ana döngüde (main loop) her kare için çağrılır.
        
        Args:
            img: BGR formatında OpenCV görüntüsü (Kameradan gelen ham görüntü).
            draw (bool): True ise landmark'ları (nokta ve çizgiler) görüntü üzerine çizer.
            
        Returns:
            img: İşlenmiş (üzerine çizim yapılmış) görüntü.
        """
        # MediaPipe RGB formatında çalışır, OpenCV BGR formatındadır. Dönüşüm yaparız.
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        
        # El algılama işlemini gerçekleştir (Inference)
        self.results = self.detector.detect(mp_image)
        
        # Eğer çizim isteniyorsa ve el bulunduysa
        if draw and self.results.hand_landmarks:
            for hand_landmarks in self.results.hand_landmarks:
                self._draw_landmarks(img, hand_landmarks)
        
        return img

    def _draw_landmarks(self, img, hand_landmarks):
        """
        Bulunan el landmark'larını görüntü üzerine çizer. (Yardımcı metod)
        """
        h, w, _ = img.shape
        
        # Landmark noktalarını (eklemleri) mor daire olarak çiz
        for landmark in hand_landmarks:
            cx, cy = int(landmark.x * w), int(landmark.y * h)
            cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)
        
        # Eklemler arasındaki bağlantıları yeşil çizgi olarak çiz
        # Bu bağlantılar elin iskeletini oluşturur
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),      # Başparmak
            (0, 5), (5, 6), (6, 7), (7, 8),      # İşaret
            (0, 9), (9, 10), (10, 11), (11, 12), # Orta
            (0, 13), (13, 14), (14, 15), (15, 16), # Yüzük
            (0, 17), (17, 18), (18, 19), (19, 20), # Serçe
            (5, 9), (9, 13), (13, 17), (0, 5), (0, 17) # Avuç içi ve bilek
        ]
        
        for start, end in connections:
            x1 = int(hand_landmarks[start].x * w)
            y1 = int(hand_landmarks[start].y * h)
            x2 = int(hand_landmarks[end].x * w)
            y2 = int(hand_landmarks[end].y * h)
            
            # Çizgiyi çiz
            cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

    def find_positions(self, img, hand_no=0):
        """
        Belirli bir elin landmark pozisyonlarını (x, y koordinatları) liste olarak döndürür.
        Ana program bu listeyi kullanarak hareketleri analiz eder.
        
        Args:
            img: BGR formatında OpenCV görüntüsü.
            hand_no (int): Hangi elin pozisyonları alınacak (0: İlk el).
            
        Returns:
            list: [(id, x, y), ...] formatında landmark listesi.
        """
        landmark_list = []
        if self.results and self.results.hand_landmarks:
            if hand_no < len(self.results.hand_landmarks):
                hand = self.results.hand_landmarks[hand_no]
                h, w, _ = img.shape
                
                # Her bir landmark için koordinatları hesapla
                for idx, lm in enumerate(hand):
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    landmark_list.append((idx, cx, cy))
        
        return landmark_list

    def fingers_up(self, landmark_list):
        """
        Hangi parmakların açık olduğunu tespit eder.
        [Başparmak, işaret, orta, yüzük, serçe] şeklinde 0 veya 1 döner.
        
        Bu proje özelinde Başparmak mantığı main.py içinde yoksayılabilir 
        ancak bu fonksiyon tüm elin durumunu döndürür.
        """
        fingers = []
        if len(landmark_list) < 21:
            return [0, 0, 0, 0, 0]
        
        # Başparmak Kontrolü (X eksenine göre açıklık kontrolü)
        if landmark_list[self.tip_ids[0]][1] < landmark_list[self.tip_ids[0] - 1][1]:
            fingers.append(1) # Açık
        else:
            fingers.append(0) # Kapalı
        
        # Diğer 4 Parmak (Y eksenine göre kontrol - Dikey)
        # Parmak ucu (tip), parmak kökünün (pip) üstündeyse açıktır.
        for i in range(1, 5):
            tip_y = landmark_list[self.tip_ids[i]][2]    # Parmak ucu Y
            pip_y = landmark_list[self.tip_ids[i] - 2][2] # Parmak kökü Y
            
            if tip_y < pip_y:
                fingers.append(1) # Açık
            else:
                fingers.append(0) # Kapalı
        
        return fingers

    def get_distance(self, landmark_list, p1, p2):
        """
        İki landmark arasındaki mesafeyi (Öklid mesafesi) hesaplar.
        Örnek: İki parmak ucu birbirine değdi mi kontrolü için kullanılır.
        """
        if len(landmark_list) < max(p1, p2) + 1:
            return -1
        
        x1, y1 = landmark_list[p1][1], landmark_list[p1][2]
        x2, y2 = landmark_list[p2][1], landmark_list[p2][2]
        
        # Pisagor teoremi
        distance = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return distance

    def get_handedness(self, hand_no=0):
        """
        Algılanan elin sağ mı sol mu olduğunu döndürür.
        ÖNEMLİ: Ayna modu (Flip) kullanıldığı için etiketlerin ters çevrilmesi gerekir.
        Burada yapılan düzeltme sayesinde Main.py içinde doğru el ismi görülür.
        
        Returns:
            str: "Right" (Sağ El) veya "Left" (Sol El).
        """
        if self.results and self.results.handedness:
            if hand_no < len(self.results.handedness):
                label = self.results.handedness[hand_no][0].category_name
                
                # Ayna modu düzeltmesi (MediaPipe mirror görüntüyü ters etiketler)
                if label == "Right": return "Left"
                if label == "Left": return "Right"
                return label 
        return None

