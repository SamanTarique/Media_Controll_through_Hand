import cv2
import mediapipe as mp
import math
import time
import pyautogui as pag
from pycaw.pycaw import AudioUtilities
import screen_brightness_control as sbc

# ==========================
# AUDIO SETUP
# ==========================
device = AudioUtilities.GetSpeakers()
volume = device.EndpointVolume

# ==========================
# CAMERA
# ==========================
video = cv2.VideoCapture(0)

# ==========================
# MEDIAPIPE
# ==========================
mp_hands = mp.solutions.hands
hand_detector = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# ==========================
# SYSTEM STATE
# ==========================
mode = "VOLUME"

prev_vol = 0.5
prev_bri = 50.0
SMOOTHING = 0.2

# Professional Gesture Lock State Tracking
active_lock = None
last_action_time = 0
action_delay = 0.6

action_text = ""
action_end = 0

# ==========================
# UI FUNCTION
# ==========================
def draw_label(img, text, x, y, color):
    cv2.rectangle(img, (x-10, y-30), (x+360, y+10), (0, 0, 0), -1)
    cv2.putText(img, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, color, 2)

# ==========================
# FINGER DETECTION
# ==========================
def fingers(hand):
    return {
        "index": hand.landmark[8].y < hand.landmark[6].y,
        "middle": hand.landmark[12].y < hand.landmark[10].y,
        "ring": hand.landmark[16].y < hand.landmark[14].y,
        "pinky": hand.landmark[20].y < hand.landmark[18].y
    }

# ==========================
# LOOP
# ==========================
while True:
    success, img = video.read()
    if not success:
        break

    img = cv2.flip(img, 1)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hand_detector.process(rgb)
    current_time = time.time()

    if results.multi_hand_landmarks:

        hand = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(img, hand, mp_hands.HAND_CONNECTIONS)

        h, w, c = img.shape

        # points
        tx, ty = int(hand.landmark[4].x*w), int(hand.landmark[4].y*h)
        ix, iy = int(hand.landmark[8].x*w), int(hand.landmark[8].y*h)
        mx, my = int(hand.landmark[12].x*w), int(hand.landmark[12].y*h)

        vol_dist = math.hypot(ix - tx, iy - ty)
        bri_dist = math.hypot(mx - tx, my - ty)

        f = fingers(hand)

        index_up = f["index"]
        middle_up = f["middle"]
        ring_up = f["ring"]
        pinky_up = f["pinky"]

        # ==========================
        # GESTURES (MEDIA CONTROL)
        # ==========================
        # 1. FIST GESTURE (Play/Pause)
        if not any(f.values()):
            if active_lock != "FIST" and (current_time - last_action_time > action_delay):
                pag.press("playpause")
                action_text = "PLAY / PAUSE"
                action_end = current_time + 1
                last_action_time = current_time
                active_lock = "FIST"

        # 2. VICTORY GESTURE (Next Track)
        elif index_up and middle_up and not ring_up and not pinky_up:
            if active_lock != "VICTORY" and (current_time - last_action_time > action_delay):
                pag.press("nexttrack")
                action_text = "NEXT TRACK"
                action_end = current_time + 1
                last_action_time = current_time
                active_lock = "VICTORY"
        
        # 3. LOCK RELEASE & MODE SWITCH
        else:
            # Clear discrete action locks if any other layout is shown
            active_lock = None
            
            # Strict validation: Only switch modes when completely clear of multi-finger frames
            if index_up and not (middle_up or ring_up or pinky_up):
                mode = "VOLUME"
            elif middle_up and not (index_up or ring_up or pinky_up):
                mode = "BRIGHTNESS"

        # ==========================
        # VOLUME CONTROL
        # ==========================
        color = (0, 255, 0) if mode == "VOLUME" else (255, 255, 0)

        # Enforce exclusivity: Do not slide volume if your hand is morphing into a Victory/Fist pose
        if mode == "VOLUME" and index_up and not (middle_up or ring_up or pinky_up):

            target = (vol_dist - 25) / 160
            target = max(0.0, min(1.0, target))

            prev_vol = prev_vol + (target - prev_vol) * SMOOTHING
            volume.SetMasterVolumeLevelScalar(prev_vol, None)

            draw_label(img, "MODE: VOLUME", 20, 50, color)
            draw_label(img, f"Volume: {int(prev_vol*100)}%", 20, 100, color)

            cv2.line(img, (tx, ty), (ix, iy), (255, 0, 255), 3)

        # ==========================
        # BRIGHTNESS CONTROL (FIXED)
        # ==========================
        # Enforce exclusivity: Do not slide brightness if hand layout is shifting
        elif mode == "BRIGHTNESS" and middle_up and not (index_up or ring_up or pinky_up):

            target = (bri_dist - 25) / 160
            target = max(0.0, min(1.0, target))

            prev_bri = prev_bri + (target*100 - prev_bri) * SMOOTHING
            brightness = int(prev_bri)

            sbc.set_brightness(brightness)

            draw_label(img, "MODE: BRIGHTNESS", 20, 50, color)
            draw_label(img, f"Brightness: {brightness}%", 20, 100, color)

            cv2.line(img, (tx, ty), (mx, my), (0, 255, 255), 3)

        # ==========================
        # ACTION TEXT
        # ==========================
        if current_time < action_end:
            draw_label(img, action_text, 20, 160, (0, 0, 255))

    cv2.imshow("FINAL HAND CONTROLLER", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()