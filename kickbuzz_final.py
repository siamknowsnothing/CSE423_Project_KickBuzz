
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import random
import sys
from dataclasses import dataclass


WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

FIELD_WIDTH = 42.0
FIELD_LENGTH = 72.0
GOAL_WIDTH = 14.0
GOAL_HEIGHT = 6.0
GOAL_DEPTH = 4.0
GALLERY_ROWS = 6
GALLERY_TIER_DEPTH = 2.3
GALLERY_TIER_HEIGHT = 1.25

PLAYER_RADIUS = 0.95
BOT_RADIUS = 0.88
BALL_RADIUS = 0.42

PLAYER_SPEED = 13.5
BOT_SPEED = 6.2
GOALKEEPER_SPEED = 7.0
BALL_FRICTION = 0.988
KICK_POWER = 23.0
STEAL_RADIUS = 1.28
MATCH_DURATION = 90.0

BG_COLOR = (0.5, 0.7, 0.9, 1.0)

# Weather system
WEATHER_SUNNY = 0
WEATHER_CLOUDY = 1
WEATHER_RAINY = 2
current_weather = WEATHER_SUNNY

# Difficulty system
DIFFICULTY_EASY = 0
DIFFICULTY_MEDIUM = 1
DIFFICULTY_HARD = 2
current_difficulty = DIFFICULTY_MEDIUM
difficulty_names = ["EASY", "MEDIUM", "HARD"]

# Shot power system
shot_charging = False
shot_power = 0.0
max_charge_time = 2.0

# Game states
GAME_STATE_DIFFICULTY_SELECT = 0
GAME_STATE_PLAYING = 1
GAME_STATE_OVER = 2
game_state = GAME_STATE_DIFFICULTY_SELECT

# Camera modes
CAMERA_MODE_DEFAULT = 0
CAMERA_MODE_FIRST_PERSON = 1
CAMERA_MODE_THIRD_PERSON = 2
camera_mode = CAMERA_MODE_DEFAULT
camera_mode_names = ["DEFAULT (Side)", "FIRST-PERSON", "THIRD-PERSON"]

# Crowd celebration
celebrating = False
celebration_timer = 0.0
CELEBRATION_DURATION = 2.5

# Goal flash effect
goal_flash = False
goal_flash_timer = 0.0
GOAL_FLASH_DURATION = 1.8

# Cheat mode
cheat_mode = False
CHEAT_PLAYER_SPEED = 15.5
CHEAT_FINISH_ZONE_Z = -24.0
CHEAT_SHOT_POWER = 34.0
CHEAT_DRIBBLE_AMPLITUDE = 7.0
CHEAT_DRIBBLE_DODGE = 3.8

# Tackle system
tackle_cooldown = 0.0
TACKLE_COOLDOWN = 0.55
TACKLE_RANGE = 2.2
TACKLE_PUSH = 7.5

keys_down = set()
last_time_ms = 0
match_time = MATCH_DURATION
score = 0
shots = 0
player_has_ball = True
game_started = False
game_over = False
freeze_timer = 0.0
status_message = "Press ENTER to start the match"
status_timer = 0.0
cam_orbit = 0.0
cam_h = 100.0



@dataclass
class Actor:
    x: float
    z: float
    radius: float
    body_color: tuple
    shorts_color: tuple
    home_x: float
    home_z: float
    role: str = "defender"
    facing_x: float = 0.0
    facing_z: float = -1.0
    anim_seed: float = 0.0


@dataclass
class Ball:
    x: float = 0.0
    z: float = 0.0
    y: float = BALL_RADIUS
    vx: float = 0.0
    vz: float = 0.0


player = Actor(
    x=0.0,
    z=24.0,
    radius=PLAYER_RADIUS,
    body_color=(0.94, 0.18, 0.18),
    shorts_color=(0.98, 0.98, 0.98),
    home_x=0.0,
    home_z=24.0,
    role="player",
    anim_seed=0.7,
)
ball = Ball()
bots = []


def clamp(value, low, high):
    return max(low, min(high, value))


def distance_2d(ax, az, bx, bz):
    return math.sqrt((ax - bx) ** 2 + (az - bz) ** 2)


def normalize_2d(x, z):
    length = math.sqrt(x * x + z * z)
    if length == 0:
        return 0.0, 0.0
    return x / length, z / length


def set_status(message, duration=1.5):
    global status_message, status_timer
    status_message = message
    status_timer = duration


def default_status():
    if not game_started:
        return "Press ENTER to start the match"
    if game_over:
        return "Match finished. Press ENTER to play again"
    if freeze_timer > 0:
        return status_message
    if cheat_mode:
        return "Cheat mode active. Auto attack and finish shot in progress"
    if player_has_ball:
        return "You have possession. Use WASD to move and SPACE to shoot"
    return "Chase, tackle the defender, and recover possession"


def create_bots():
    global bots
    bots = []

    formation = [
        (0.0, -31.0, "goalkeeper"),
        (-12.0, -18.5, "defender"),
        (0.0, -17.0, "defender"),
        (12.0, -18.5, "defender"),
        (-7.0, -6.5, "midfielder"),
        (7.0, -6.5, "midfielder"),
    ]

    for i, (x, z, role) in enumerate(formation):
        if role == "goalkeeper":
            body = (0.95, 0.84, 0.22)
            shorts = (0.10, 0.10, 0.10)
        else:
            body = (0.18, 0.30 + random.random() * 0.08, 0.88)
            shorts = (0.08, 0.08, 0.18)

        bots.append(
            Actor(
                x=x,
                z=z,
                radius=BOT_RADIUS,
                body_color=body,
                shorts_color=shorts,
                home_x=x,
                home_z=z,
                role=role,
                anim_seed=0.4 * i,
            )
        )


def attach_ball_to_player():
    ball.x = player.x + player.facing_x * 0.95
    ball.z = player.z + player.facing_z * 0.95
    ball.y = BALL_RADIUS
    ball.vx = 0.0
    ball.vz = 0.0


def reset_positions(full_reset=False):
    global score, shots, player_has_ball, freeze_timer

    player.x = 0.0
    player.z = 24.0
    player.facing_x = 0.0
    player.facing_z = -1.0

    player_has_ball = True
    ball.x = 0.0
    ball.z = 22.8
    ball.vx = 0.0
    ball.vz = 0.0
    attach_ball_to_player()

    create_bots()
    freeze_timer = 0.0

    if full_reset:
        score = 0
        shots = 0


def start_new_match():
    global match_time, game_started, game_over, game_state
    match_time = MATCH_DURATION
    game_started = True
    game_over = False
    game_state = GAME_STATE_PLAYING
    reset_positions(full_reset=True)
    set_status("Match started. Score as many goals as you can!", 2.0)


def setup_graphics():
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LEQUAL)
    glClearDepth(1.0)
    glDisable(GL_CULL_FACE)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(*BG_COLOR)


def setup_projection():
    glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(58.0, WINDOW_WIDTH / max(1, WINDOW_HEIGHT), 0.1, 2000.0)
    glMatrixMode(GL_MODELVIEW)


def begin_2d():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()


def end_2d():
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1, 1, 1)):
    glColor3f(*color)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))


def get_bitmap_text_width(text, font=GLUT_BITMAP_HELVETICA_18):
    width = 0
    for ch in text:
        width += glutBitmapWidth(font, ord(ch))
    return width


def draw_text_centered(x_center, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1, 1, 1)):
    text_width = get_bitmap_text_width(text, font)
    draw_text(x_center - text_width / 2, y, text, font, color)


def draw_stroke_text_2d(x, y, text, scale=0.2, color=(1, 1, 1), line_width=3.0):
    glColor3f(*color)
    glPushMatrix()
    glTranslatef(x, y, 0.0)
    glScalef(scale, scale, 1.0)
    glLineWidth(line_width)
    for ch in text:
        glutStrokeCharacter(GLUT_STROKE_ROMAN, ord(ch))
    glPopMatrix()


def get_stroke_text_width(text, font=GLUT_STROKE_ROMAN):
    width = 0
    for ch in text:
        width += glutStrokeWidth(font, ord(ch))
    return width


def draw_panel(x, y, w, h, color):
    glColor4f(*color)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()


def draw_circle_xz(cx, cz, radius, y=0.02, segments=40, filled=False):
    mode = GL_POLYGON if filled else GL_LINE_LOOP
    glBegin(mode)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        glVertex3f(cx + math.cos(angle) * radius, y, cz + math.sin(angle) * radius)
    glEnd()


def draw_arc_xz(cx, cz, radius, angle_start, angle_end, y=0.02, segments=36):
    glBegin(GL_LINE_STRIP)
    for i in range(segments + 1):
        t = i / segments
        angle = math.radians(angle_start + (angle_end - angle_start) * t)
        glVertex3f(cx + math.cos(angle) * radius, y, cz + math.sin(angle) * radius)
    glEnd()


# ============== WEATHER RENDERING ==============
def draw_sun(x, y, z, radius=8.0):
    """Draw a sun as a yellow circle with rays."""
    glColor3f(1.0, 0.95, 0.2)
    glBegin(GL_POLYGON)
    for i in range(32):
        angle = 2 * math.pi * i / 32
        glVertex3f(x + math.cos(angle) * radius, y, z + math.sin(angle) * radius)
    glEnd()
    
    glBegin(GL_LINES)
    for i in range(12):
        angle = 2 * math.pi * i / 12
        ray_len = radius + 3.0
        glVertex3f(x + math.cos(angle) * radius, y, z + math.sin(angle) * radius)
        glVertex3f(x + math.cos(angle) * ray_len, y, z + math.sin(angle) * ray_len)
    glEnd()


def draw_cloud(cx, cy, cz, scale=1.0):
    """Draw a cloud as overlapping white ellipses."""
    glColor3f(0.95, 0.95, 1.0)
    for ox in [-2.0, 0.0, 2.0]:
        glBegin(GL_POLYGON)
        for i in range(24):
            angle = 2 * math.pi * i / 24
            x = cx + ox + math.cos(angle) * 3.0 * scale
            z = cz + math.sin(angle) * 1.5 * scale
            glVertex3f(x, cy, z)
        glEnd()


def draw_sun_2d(x, y, radius=24):
    glColor3f(1.0, 0.92, 0.22)
    glBegin(GL_POLYGON)
    for i in range(32):
        angle = 2 * math.pi * i / 32
        glVertex2f(x + math.cos(angle) * radius, y + math.sin(angle) * radius)
    glEnd()

    glLineWidth(2.0)
    glBegin(GL_LINES)
    for i in range(12):
        angle = 2 * math.pi * i / 12
        inner = radius + 6
        outer = radius + 16
        glVertex2f(x + math.cos(angle) * inner, y + math.sin(angle) * inner)
        glVertex2f(x + math.cos(angle) * outer, y + math.sin(angle) * outer)
    glEnd()


def draw_cloud_2d(x, y, scale=1.0):
    cloud_parts = [
        (0, 0, 26),
        (-24, -3, 18),
        (24, -2, 20),
        (-8, 12, 16),
        (14, 10, 17),
    ]
    glColor4f(0.96, 0.97, 1.0, 0.95)
    for ox, oy, r in cloud_parts:
        glBegin(GL_POLYGON)
        for i in range(28):
            angle = 2 * math.pi * i / 28
            glVertex2f(
                x + ox * scale + math.cos(angle) * r * scale,
                y + oy * scale + math.sin(angle) * r * 0.75 * scale,
            )
        glEnd()


def draw_weather_overlay():
    """2D weather overlay so sun/cloud/rain stay visible in third-person view."""
    begin_2d()

    anchor_x = WINDOW_WIDTH - 110
    anchor_y = WINDOW_HEIGHT - 92

    if current_weather == WEATHER_SUNNY:
        draw_sun_2d(anchor_x, anchor_y, 24)
    elif current_weather == WEATHER_CLOUDY:
        draw_cloud_2d(anchor_x, anchor_y, 1.0)
    else:
        draw_cloud_2d(anchor_x, anchor_y + 8, 1.05)
        glColor3f(0.62, 0.76, 0.95)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        for dx in (-22, -10, 2, 14, 26):
            glVertex2f(anchor_x + dx, anchor_y - 12)
            glVertex2f(anchor_x + dx - 4, anchor_y - 28)
        glEnd()

    end_2d()


def get_weather_anchor():
    """Place weather effects where they remain visible in gameplay camera views."""
    rad = math.radians(cam_orbit)

    if camera_mode == CAMERA_MODE_THIRD_PERSON:
        dist = 30.0 + (cam_h * 0.05)
        cam_x = player.x + dist * math.sin(rad)
        cam_z = player.z + dist * math.cos(rad)
        dir_x, dir_z = normalize_2d(player.x - cam_x, player.z - cam_z)
        right_x, right_z = dir_z, -dir_x
        return (
            player.x + dir_x * 42.0 + right_x * 22.0,
            74.0,
            player.z + dir_z * 42.0 + right_z * 22.0,
        )

    if camera_mode == CAMERA_MODE_FIRST_PERSON:
        player_angle = math.atan2(player.facing_x, player.facing_z) + rad
        dir_x = math.sin(player_angle)
        dir_z = math.cos(player_angle)
        right_x, right_z = dir_z, -dir_x
        return (
            player.x + dir_x * 48.0 + right_x * 18.0,
            76.0,
            player.z + dir_z * 48.0 + right_z * 18.0,
        )

    # Default/side view
    dir_x, dir_z = normalize_2d(-math.sin(rad), -math.cos(rad))
    right_x, right_z = dir_z, -dir_x
    return (
        player.x + dir_x * 36.0 + right_x * 24.0,
        74.0,
        player.z + dir_z * 36.0 + right_z * 24.0,
    )


def draw_rain(center_x, center_z):
    """Draw rain as short diagonal lines around the active play view."""
    glColor3f(0.6, 0.7, 0.9)
    glLineWidth(1.4)
    rain_time = glutGet(GLUT_ELAPSED_TIME) * 0.001
    
    glBegin(GL_LINES)
    start_x = int(center_x) - 70
    end_x = int(center_x) + 71
    start_z = int(center_z) - 85
    end_z = int(center_z) + 86
    for x in range(start_x, end_x, 14):
        for z in range(start_z, end_z, 14):
            rain_y_offset = math.fmod(rain_time * 40.0 + x + z, 80.0)
            rain_y = 92.0 - rain_y_offset
            glVertex3f(x, rain_y, z)
            glVertex3f(x + 2.6, rain_y - 5.5, z + 0.5)
    glEnd()
    glLineWidth(1.0)


def draw_sky_with_weather():
    """Draw a full sky enclosure with weather effects."""
    glDisable(GL_DEPTH_TEST)
    glPushMatrix()
    
    # Scale sky based on weather colors
    if current_weather == WEATHER_SUNNY:
        c1 = (0.6, 0.8, 1.0) # Bottom
        c2 = (0.8, 0.9, 1.0) # Top
    elif current_weather == WEATHER_CLOUDY:
        c1 = (0.4, 0.5, 0.7)
        c2 = (0.6, 0.7, 0.9)
    else: # RAINY
        c1 = (0.25, 0.3, 0.45)
        c2 = (0.4, 0.45, 0.6)

    size = 1000.0
    h_min = -250.0
    h_max = 600.0

    glBegin(GL_QUADS)
    # Front
    glColor3f(*c1); glVertex3f(-size, h_min, -size)
    glColor3f(*c1); glVertex3f(size, h_min, -size)
    glColor3f(*c2); glVertex3f(size, h_max, -size)
    glColor3f(*c2); glVertex3f(-size, h_max, -size)
    
    # Back
    glColor3f(*c1); glVertex3f(-size, h_min, size)
    glColor3f(*c1); glVertex3f(size, h_min, size)
    glColor3f(*c2); glVertex3f(size, h_max, size)
    glColor3f(*c2); glVertex3f(-size, h_max, size)
    
    # Left
    glColor3f(*c1); glVertex3f(-size, h_min, -size)
    glColor3f(*c1); glVertex3f(-size, h_min, size)
    glColor3f(*c2); glVertex3f(-size, h_max, size)
    glColor3f(*c2); glVertex3f(-size, h_max, -size)
    
    # Right
    glColor3f(*c1); glVertex3f(size, h_min, -size)
    glColor3f(*c1); glVertex3f(size, h_min, size)
    glColor3f(*c2); glVertex3f(size, h_max, size)
    glColor3f(*c2); glVertex3f(size, h_max, -size)
    
    # Top
    glColor3f(*c2)
    glVertex3f(-size, h_max, -size)
    glVertex3f(size, h_max, -size)
    glVertex3f(size, h_max, size)
    glVertex3f(-size, h_max, size)
    glEnd()
    
    glPopMatrix()

    # Keep weather objects at fixed world positions high above the stadium,
    # with a first-person placement that keeps them visible near the upper
    # middle sky area from the player's view.
    if current_weather == WEATHER_SUNNY:
        if camera_mode == CAMERA_MODE_FIRST_PERSON:
            draw_sun(0.0, 82.5, -205.0, 26.0)
        else:
            draw_sun(-10.0, 92.5, -260.0, 24.0)
    elif current_weather == WEATHER_CLOUDY:
        if camera_mode == CAMERA_MODE_FIRST_PERSON:
            draw_cloud(0.0, 82.5, -205.0, 2.5)
            draw_cloud(-50.0, 77.0, -190.0, 2.0)
            draw_cloud(52.0, 78.0, -220.0, 2.1)
        else:
            draw_cloud(0.0, 92.5, -255.0, 3.0)
            draw_cloud(-62.0, 86.0, -235.0, 2.4)
            draw_cloud(68.0, 88.0, -275.0, 2.6)
    elif current_weather == WEATHER_RAINY:
        if camera_mode == CAMERA_MODE_FIRST_PERSON:
            draw_cloud(0.0, 82.0, -198.0, 2.7)
            draw_cloud(-48.0, 76.5, -186.0, 2.1)
            draw_cloud(50.0, 77.5, -214.0, 2.2)
        else:
            draw_cloud(0.0, 91.0, -245.0, 3.2)
            draw_cloud(-58.0, 85.0, -225.0, 2.5)
            draw_cloud(62.0, 87.0, -265.0, 2.7)
        draw_rain(player.x, player.z - 8.0)
    
    glEnable(GL_DEPTH_TEST)


def draw_sky():
    """Wrapper for sky rendering (now includes weather)."""
    draw_sky_with_weather()


def draw_field():
    half_w = FIELD_WIDTH / 2
    half_l = FIELD_LENGTH / 2

    glColor3f(0.12, 0.12, 0.11)
    glBegin(GL_QUADS)
    glVertex3f(-half_w - 5, -0.03, -half_l - 5)
    glVertex3f(half_w + 5, -0.03, -half_l - 5)
    glVertex3f(half_w + 5, -0.03, half_l + 5)
    glVertex3f(-half_w - 5, -0.03, half_l + 5)
    glEnd()

    # Broadcast-style pitch stripes
    stripe_count = 10
    stripe_len = FIELD_LENGTH / stripe_count
    for i in range(stripe_count):
        z1 = -half_l + i * stripe_len
        z2 = z1 + stripe_len
        if i % 2 == 0:
            glColor3f(0.16, 0.50, 0.14)
        else:
            glColor3f(0.19, 0.58, 0.17)
        glBegin(GL_QUADS)
        glVertex3f(-half_w, 0.0, z1)
        glVertex3f(half_w, 0.0, z1)
        glVertex3f(half_w, 0.0, z2)
        glVertex3f(-half_w, 0.0, z2)
        glEnd()

    # Subtle center gloss
    glColor4f(0.45, 0.80, 0.35, 0.08)
    glBegin(GL_QUADS)
    glVertex3f(-half_w, 0.01, -half_l)
    glVertex3f(half_w, 0.01, -half_l)
    glVertex3f(half_w, 0.01, half_l)
    glVertex3f(-half_w, 0.01, half_l)
    glEnd()

    glColor3f(1.0, 1.0, 1.0)
    glLineWidth(2.8)
    glBegin(GL_LINE_LOOP)
    glVertex3f(-half_w, 0.02, -half_l)
    glVertex3f(half_w, 0.02, -half_l)
    glVertex3f(half_w, 0.02, half_l)
    glVertex3f(-half_w, 0.02, half_l)
    glEnd()

    glBegin(GL_LINES)
    glVertex3f(-half_w, 0.02, 0)
    glVertex3f(half_w, 0.02, 0)
    glEnd()

    draw_circle_xz(0.0, 0.0, 5.2)

    glBegin(GL_LINE_LOOP)
    glVertex3f(-11.0, 0.02, -half_l)
    glVertex3f(11.0, 0.02, -half_l)
    glVertex3f(11.0, 0.02, -half_l + 11.0)
    glVertex3f(-11.0, 0.02, -half_l + 11.0)
    glEnd()

    glBegin(GL_LINE_LOOP)
    glVertex3f(-5.5, 0.02, -half_l)
    glVertex3f(5.5, 0.02, -half_l)
    glVertex3f(5.5, 0.02, -half_l + 5.5)
    glVertex3f(-5.5, 0.02, -half_l + 5.5)
    glEnd()

    glPointSize(5)
    glBegin(GL_POINTS)
    glVertex3f(0.0, 0.02, -half_l + 8.5)
    glVertex3f(0.0, 0.02, 0.0)
    glEnd()

    draw_arc_xz(0.0, -half_l + 8.5, 4.1, 220, 320)


def draw_goal():
    half_w = GOAL_WIDTH / 2
    goal_front_z = -FIELD_LENGTH / 2
    goal_back_z = goal_front_z - GOAL_DEPTH

    glColor3f(1.0, 1.0, 1.0)
    glLineWidth(3.0)
    glBegin(GL_LINES)
    glVertex3f(-half_w, 0.0, goal_front_z)
    glVertex3f(-half_w, GOAL_HEIGHT, goal_front_z)
    glVertex3f(half_w, 0.0, goal_front_z)
    glVertex3f(half_w, GOAL_HEIGHT, goal_front_z)
    glVertex3f(-half_w, GOAL_HEIGHT, goal_front_z)
    glVertex3f(half_w, GOAL_HEIGHT, goal_front_z)

    glVertex3f(-half_w, 0.0, goal_front_z)
    glVertex3f(-half_w, 0.0, goal_back_z)
    glVertex3f(half_w, 0.0, goal_front_z)
    glVertex3f(half_w, 0.0, goal_back_z)
    glVertex3f(-half_w, GOAL_HEIGHT, goal_front_z)
    glVertex3f(-half_w, GOAL_HEIGHT, goal_back_z)
    glVertex3f(half_w, GOAL_HEIGHT, goal_front_z)
    glVertex3f(half_w, GOAL_HEIGHT, goal_back_z)
    glVertex3f(-half_w, GOAL_HEIGHT, goal_back_z)
    glVertex3f(half_w, GOAL_HEIGHT, goal_back_z)
    glEnd()

    # Better goal net: back mesh + roof mesh + side meshes
    glColor4f(0.84, 0.92, 1.0, 0.42)
    glLineWidth(1.2)

    # Back net verticals
    glBegin(GL_LINES)
    for i in range(0, 8):
        x = -half_w + (GOAL_WIDTH * i / 7.0)
        glVertex3f(x, 0.0, goal_back_z)
        glVertex3f(x, GOAL_HEIGHT, goal_back_z)

    # Back net horizontals
    for j in range(0, 6):
        y = GOAL_HEIGHT * j / 5.0
        glVertex3f(-half_w, y, goal_back_z)
        glVertex3f(half_w, y, goal_back_z)

    # Roof net lines from front to back
    for i in range(0, 8):
        x = -half_w + (GOAL_WIDTH * i / 7.0)
        glVertex3f(x, GOAL_HEIGHT, goal_front_z)
        glVertex3f(x, GOAL_HEIGHT, goal_back_z)

    # Roof net cross-lines
    for k in range(0, 5):
        z = goal_front_z - (GOAL_DEPTH * k / 4.0)
        glVertex3f(-half_w, GOAL_HEIGHT, z)
        glVertex3f(half_w, GOAL_HEIGHT, z)

    # Left side net
    for j in range(0, 6):
        y = GOAL_HEIGHT * j / 5.0
        glVertex3f(-half_w, y, goal_front_z)
        glVertex3f(-half_w, y, goal_back_z)
    for k in range(0, 5):
        z = goal_front_z - (GOAL_DEPTH * k / 4.0)
        glVertex3f(-half_w, 0.0, z)
        glVertex3f(-half_w, GOAL_HEIGHT, z)

    # Right side net
    for j in range(0, 6):
        y = GOAL_HEIGHT * j / 5.0
        glVertex3f(half_w, y, goal_front_z)
        glVertex3f(half_w, y, goal_back_z)
    for k in range(0, 5):
        z = goal_front_z - (GOAL_DEPTH * k / 4.0)
        glVertex3f(half_w, 0.0, z)
        glVertex3f(half_w, GOAL_HEIGHT, z)
    glEnd()


def ball_is_goal():
    goal_half_inner = GOAL_WIDTH / 2 - BALL_RADIUS * 0.55
    goal_line_z = -FIELD_LENGTH / 2
    below_crossbar = (ball.y + BALL_RADIUS) <= GOAL_HEIGHT
    between_posts = abs(ball.x) <= goal_half_inner
    crossed_goal_line = ball.z <= goal_line_z
    return between_posts and below_crossbar and crossed_goal_line


def draw_stadium():
    """Draw a richer stadium with clearer side galleries, roof bands, and structure."""
    half_w = FIELD_WIDTH / 2 + 8.5
    half_l = FIELD_LENGTH / 2 + 5.0
    rows = GALLERY_ROWS
    tier_w = GALLERY_TIER_DEPTH
    tier_h = GALLERY_TIER_HEIGHT
    stand_top = rows * tier_h

    # Outer street / asphalt ground around the stadium so the surroundings
    # look like roads instead of light blue empty space.
    street_half_w = half_w + rows * tier_w + 18.0
    street_half_l = half_l + 22.0
    glColor3f(0.32, 0.35, 0.37)
    glBegin(GL_QUADS)
    glVertex3f(-street_half_w, -0.04, -street_half_l)
    glVertex3f(street_half_w, -0.04, -street_half_l)
    glVertex3f(street_half_w, -0.04, street_half_l)
    glVertex3f(-street_half_w, -0.04, street_half_l)
    glEnd()

    # Pitch-side walkways to visually separate the gallery from the turf.
    glColor3f(0.10, 0.11, 0.13)
    glBegin(GL_QUADS)
    glVertex3f(-half_w, 0.01, -half_l)
    glVertex3f(-FIELD_WIDTH / 2 - 0.6, 0.01, -half_l)
    glVertex3f(-FIELD_WIDTH / 2 - 0.6, 0.01, half_l)
    glVertex3f(-half_w, 0.01, half_l)

    glVertex3f(FIELD_WIDTH / 2 + 0.6, 0.01, -half_l)
    glVertex3f(half_w, 0.01, -half_l)
    glVertex3f(half_w, 0.01, half_l)
    glVertex3f(FIELD_WIDTH / 2 + 0.6, 0.01, half_l)
    glEnd()

    for side in (-1, 1):
        inner_x = side * half_w
        outer_x = side * (half_w + rows * tier_w)
        roof_inner_x = inner_x + side * (tier_w * 1.2)
        roof_outer_x = outer_x + side * 4.5
        aisle_z_1 = -half_l * 0.28
        aisle_z_2 = half_l * 0.30

        for r in range(rows):
            seat_front_x = inner_x + side * (r * tier_w)
            seat_back_x = inner_x + side * ((r + 1) * tier_w)
            seat_y = r * tier_h
            riser_top = seat_y + tier_h

            if r % 2 == 0:
                seat_color = (0.33, 0.35, 0.39)
                riser_color = (0.24, 0.26, 0.30)
            else:
                seat_color = (0.29, 0.31, 0.35)
                riser_color = (0.20, 0.22, 0.26)

            # Seating tread
            glColor3f(*seat_color)
            glBegin(GL_QUADS)
            glVertex3f(seat_front_x, seat_y, -half_l)
            glVertex3f(seat_back_x, seat_y, -half_l)
            glVertex3f(seat_back_x, seat_y, half_l)
            glVertex3f(seat_front_x, seat_y, half_l)
            glEnd()

            # Front riser
            glColor3f(*riser_color)
            glBegin(GL_QUADS)
            glVertex3f(seat_back_x, seat_y, -half_l)
            glVertex3f(seat_back_x, riser_top, -half_l)
            glVertex3f(seat_back_x, riser_top, half_l)
            glVertex3f(seat_back_x, seat_y, half_l)
            glEnd()

            # Seat strip for extra definition
            glColor3f(0.13, 0.14, 0.17)
            strip_front = seat_front_x + side * (tier_w * 0.18)
            strip_back = seat_front_x + side * (tier_w * 0.36)
            glBegin(GL_QUADS)
            glVertex3f(strip_front, seat_y + 0.06, -half_l)
            glVertex3f(strip_back, seat_y + 0.06, -half_l)
            glVertex3f(strip_back, seat_y + 0.06, half_l)
            glVertex3f(strip_front, seat_y + 0.06, half_l)
            glEnd()

            # Two aisle breaks so the gallery is not a single flat slab.
            glColor3f(0.82, 0.76, 0.34)
            aisle_front = seat_front_x + side * (tier_w * 0.58)
            aisle_back = seat_front_x + side * (tier_w * 0.76)
            glBegin(GL_QUADS)
            glVertex3f(aisle_front, seat_y + 0.08, aisle_z_1 - 1.1)
            glVertex3f(aisle_back, seat_y + 0.08, aisle_z_1 - 1.1)
            glVertex3f(aisle_back, seat_y + 0.08, aisle_z_1 + 1.1)
            glVertex3f(aisle_front, seat_y + 0.08, aisle_z_1 + 1.1)

            glVertex3f(aisle_front, seat_y + 0.08, aisle_z_2 - 1.1)
            glVertex3f(aisle_back, seat_y + 0.08, aisle_z_2 - 1.1)
            glVertex3f(aisle_back, seat_y + 0.08, aisle_z_2 + 1.1)
            glVertex3f(aisle_front, seat_y + 0.08, aisle_z_2 + 1.1)
            glEnd()

        # Back wall
        glColor3f(0.11, 0.13, 0.17)
        wall_front_x = outer_x
        wall_back_x = outer_x + side * 2.2
        glBegin(GL_QUADS)
        glVertex3f(wall_front_x, 0.0, -half_l - 6.0)
        glVertex3f(wall_back_x, 0.0, -half_l - 8.0)
        glVertex3f(wall_back_x, stand_top + 4.8, half_l + 8.0)
        glVertex3f(wall_front_x, stand_top + 4.8, half_l + 6.0)
        glEnd()

        # Roof canopy
        glColor3f(0.18, 0.21, 0.28)
        roof_y = stand_top + 4.3
        glBegin(GL_QUADS)
        glVertex3f(roof_inner_x, roof_y, -half_l - 7.5)
        glVertex3f(roof_outer_x, roof_y + 1.5, -half_l - 10.5)
        glVertex3f(roof_outer_x, roof_y + 1.5, half_l + 10.5)
        glVertex3f(roof_inner_x, roof_y, half_l + 7.5)
        glEnd()

        # Roof underside shadow band
        glColor3f(0.08, 0.09, 0.11)
        glBegin(GL_QUADS)
        glVertex3f(roof_inner_x, roof_y - 0.35, -half_l - 7.5)
        glVertex3f(roof_outer_x, roof_y + 1.05, -half_l - 10.5)
        glVertex3f(roof_outer_x, roof_y + 1.05, half_l + 10.5)
        glVertex3f(roof_inner_x, roof_y - 0.35, half_l + 7.5)
        glEnd()

        # Vertical supports
        glColor3f(0.23, 0.25, 0.29)
        support_x_front = inner_x + side * (rows * tier_w * 0.55)
        support_x_back = support_x_front + side * 0.55
        for z in (-half_l - 2.0, -half_l * 0.35, 0.0, half_l * 0.35, half_l + 2.0):
            glBegin(GL_QUADS)
            glVertex3f(support_x_front, 0.0, z - 0.35)
            glVertex3f(support_x_back, 0.0, z - 0.35)
            glVertex3f(support_x_back, roof_y + 0.35, z + 0.35)
            glVertex3f(support_x_front, roof_y + 0.35, z + 0.35)
            glEnd()

        # Guard rail on the front edge of the top tier
        rail_x = inner_x + side * 0.2
        glColor3f(0.78, 0.80, 0.86)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex3f(rail_x, 1.0, -half_l)
        glVertex3f(rail_x, 1.0, half_l)
        glVertex3f(rail_x + side * (rows * tier_w * 0.08), 2.2, -half_l)
        glVertex3f(rail_x + side * (rows * tier_w * 0.08), 2.2, half_l)
        glEnd()

    # End structures behind both goals
    glColor3f(0.19, 0.21, 0.26)
    glBegin(GL_QUADS)
    glVertex3f(-half_w + 2.0, 0.0, -half_l - 10.0)
    glVertex3f(half_w - 2.0, 0.0, -half_l - 10.0)
    glVertex3f(half_w - 5.5, 5.3, -half_l - 1.8)
    glVertex3f(-half_w + 5.5, 5.3, -half_l - 1.8)

    glVertex3f(-half_w + 2.0, 0.0, half_l + 1.8)
    glVertex3f(half_w - 2.0, 0.0, half_l + 1.8)
    glVertex3f(half_w - 5.5, 5.3, half_l + 10.0)
    glVertex3f(-half_w + 5.5, 5.3, half_l + 10.0)
    glEnd()


def draw_shadow(x, z, radius):
    glColor4f(0.03, 0.03, 0.03, 0.28)
    glBegin(GL_POLYGON)
    for i in range(24):
        angle = 2 * math.pi * i / 24
        glVertex3f(x + math.cos(angle) * radius, 0.03, z + math.sin(angle) * radius * 0.75)
    glEnd()


def draw_human(actor, is_player=False):
    facing_angle = math.degrees(math.atan2(actor.facing_x, actor.facing_z))
    skin = (0.93, 0.78, 0.63)
    boot = (0.05, 0.05, 0.05)

    speed_hint = abs(actor.facing_x) + abs(actor.facing_z)
    anim_time = glutGet(GLUT_ELAPSED_TIME) * 0.011 + actor.anim_seed
    leg_swing = math.sin(anim_time) * 20.0 * speed_hint
    arm_swing = -leg_swing * 0.8

    glPushMatrix()
    glTranslatef(actor.x, 0.0, actor.z)
    glRotatef(facing_angle, 0.0, 1.0, 0.0)

    glColor3f(*skin)
    glPushMatrix()
    glTranslatef(0.0, 3.45, 0.0)
    glutSolidSphere(0.34, 14, 14)
    glPopMatrix()

    glColor3f(*actor.body_color)
    glPushMatrix()
    glTranslatef(0.0, 2.32, 0.0)
    glScalef(0.90, 1.45, 0.50)
    glutSolidCube(1.0)
    glPopMatrix()

    glColor3f(*actor.shorts_color)
    glPushMatrix()
    glTranslatef(0.0, 1.45, 0.0)
    glScalef(0.85, 0.55, 0.50)
    glutSolidCube(1.0)
    glPopMatrix()

    for side in (-1, 1):
        glColor3f(*skin)
        glPushMatrix()
        glTranslatef(0.54 * side, 2.62, 0.0)
        glRotatef(side * arm_swing, 1.0, 0.0, 0.0)
        glTranslatef(0.0, -0.55, 0.0)
        glScalef(0.18, 1.08, 0.18)
        glutSolidCube(1.0)
        glPopMatrix()

        glColor3f(*actor.shorts_color)
        glPushMatrix()
        glTranslatef(0.26 * side, 1.00, 0.0)
        glRotatef(-side * leg_swing, 1.0, 0.0, 0.0)
        glTranslatef(0.0, -0.28, 0.0)
        glScalef(0.22, 0.56, 0.22)
        glutSolidCube(1.0)
        glPopMatrix()

        glColor3f(*skin)
        glPushMatrix()
        glTranslatef(0.26 * side, 0.44, 0.02)
        glRotatef(-side * leg_swing * 0.7, 1.0, 0.0, 0.0)
        glTranslatef(0.0, -0.42, 0.0)
        glScalef(0.20, 0.82, 0.20)
        glutSolidCube(1.0)
        glPopMatrix()

        glColor3f(*boot)
        glPushMatrix()
        glTranslatef(0.26 * side, 0.03, 0.12)
        glScalef(0.24, 0.12, 0.42)
        glutSolidCube(1.0)
        glPopMatrix()

    if is_player:
        glColor3f(1.0, 0.95, 0.22)
        glPushMatrix()
        glTranslatef(0.0, 4.05, 0.0)
        glScalef(0.75, 0.10, 0.75)
        glutSolidCube(1.0)
        glPopMatrix()

    glPopMatrix()


def draw_ball():
    glPushMatrix()
    glTranslatef(ball.x, ball.y, ball.z)
    glRotatef(glutGet(GLUT_ELAPSED_TIME) * 0.08, 0.0, 1.0, 0.0)

    # Natural football base color
    glColor3f(0.96, 0.96, 0.94)
    glutSolidSphere(BALL_RADIUS, 24, 24)

    # Dark patches to imitate a real football panel pattern
    glColor3f(0.09, 0.09, 0.10)
    patch_positions = [
        (0.0, 0.23, 0.0),
        (0.18, 0.08, 0.22),
        (-0.18, 0.08, 0.22),
        (0.22, -0.06, -0.10),
        (-0.22, -0.06, -0.10),
        (0.0, -0.18, 0.18),
    ]
    for px, py, pz in patch_positions:
        glPushMatrix()
        glTranslatef(px, py, pz)
        glScalef(1.0, 0.55, 1.0)
        glutSolidSphere(0.085, 12, 12)
        glPopMatrix()

    # Soft seam / shadow accents
    glColor3f(0.70, 0.70, 0.70)
    for px, py, pz in [(0.0, 0.0, 0.30), (0.24, 0.0, 0.0), (-0.24, 0.0, 0.0), (0.0, -0.20, -0.12)]:
        glPushMatrix()
        glTranslatef(px, py, pz)
        glScalef(0.9, 0.35, 0.9)
        glutSolidSphere(0.05, 10, 10)
        glPopMatrix()
    glPopMatrix()


# ============== CROWD RENDERING ==============
def draw_crowd_person(x, y, z, team_color, jump_offset=0.0):
    """Draw a simple crowd person (head + body)."""
    glPushMatrix()
    glTranslatef(x, y + jump_offset, z)
    
    glColor3f(*team_color)
    glPushMatrix()
    glScalef(0.45, 0.9, 0.45)
    glutSolidCube(1.0)
    glPopMatrix()
    
    glColor3f(0.9, 0.7, 0.5)
    glPushMatrix()
    glTranslatef(0.0, 0.65, 0.0)
    glutSolidSphere(0.28, 10, 10)
    glPopMatrix()
    
    glPopMatrix()


def draw_crowd():
    """Draw a full crowd along both side galleries with synchronized celebration."""
    half_w = FIELD_WIDTH / 2 + 8.5
    field_l = FIELD_LENGTH

    # Calculate jump offset if celebrating
    jump_offset = 0.0
    if celebrating and celebration_timer > 0:
        progress = 1.0 - (celebration_timer / CELEBRATION_DURATION)
        jump_offset = math.sin(progress * math.pi * 3.0) * 1.5

    spacing_z = 2.15
    rows = GALLERY_ROWS
    tier_w = GALLERY_TIER_DEPTH
    tier_h = GALLERY_TIER_HEIGHT

    # Left Gallery (Home)
    team_color_home = (0.2, 0.4, 0.9)
    for row in range(rows):
        z_start = -field_l / 2 + 2.5 + (row % 2) * 0.6
        z_end = field_l / 2 - 2.5
        curr_z = z_start
        while curr_z <= z_end:
            x = -half_w - row * tier_w - tier_w * 0.58
            y = 0.95 + row * tier_h
            draw_crowd_person(x, y, curr_z, team_color_home, jump_offset)
            curr_z += spacing_z

    # Right Gallery (Away)
    team_color_away = (0.9, 0.2, 0.2)
    for row in range(rows):
        z_start = -field_l / 2 + 2.5 + ((row + 1) % 2) * 0.6
        z_end = field_l / 2 - 2.5
        curr_z = z_start
        while curr_z <= z_end:
            x = half_w + row * tier_w + tier_w * 0.58
            y = 0.95 + row * tier_h
            draw_crowd_person(x, y, curr_z, team_color_away, jump_offset)
            curr_z += spacing_z


# ============== SHOT POWER BAR ==============
def draw_shot_power_bar():
    """Draw the shot power bar when charging."""
    if not shot_charging or not player_has_ball:
        return
    
    begin_2d()
    
    bar_x = WINDOW_WIDTH / 2 - 75
    bar_y = 150
    bar_width = 150
    bar_height = 30
    
    draw_panel(bar_x - 10, bar_y - 10, bar_width + 20, bar_height + 20, (0.05, 0.05, 0.10, 0.7))
    
    glColor3f(0.9, 0.9, 1.0)
    glLineWidth(2.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_width, bar_y)
    glVertex2f(bar_x + bar_width, bar_y + bar_height)
    glVertex2f(bar_x, bar_y + bar_height)
    glEnd()
    
    fill_width = bar_width * shot_power
    if shot_power < 0.5:
        r = shot_power * 2
        g = 1.0
        b = 0.0
    else:
        r = 1.0
        g = 2.0 * (1.0 - shot_power)
        b = 0.0
    
    glColor3f(r, g, b)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + fill_width, bar_y)
    glVertex2f(bar_x + fill_width, bar_y + bar_height)
    glVertex2f(bar_x, bar_y + bar_height)
    glEnd()
    
    power_percent = int(shot_power * 100)
    draw_text(bar_x + bar_width / 2 - 30, bar_y + bar_height + 10, f"Power: {power_percent}%", 
              font=GLUT_BITMAP_HELVETICA_18, color=(1.0, 1.0, 1.0))
    
    end_2d()


# ============== GOAL FLASH EFFECT ==============
def draw_goal_flash():
    """Draw a flash overlay plus a big GOAL text effect when a goal is scored."""
    if not goal_flash or goal_flash_timer <= 0:
        return
    
    begin_2d()
    
    progress = 1.0 - (goal_flash_timer / GOAL_FLASH_DURATION)
    fade = goal_flash_timer / GOAL_FLASH_DURATION
    alpha = 0.22 + fade * 0.35
    pulse = 0.5 + 0.5 * math.sin(progress * math.pi * 8.0)
    glow_alpha = 0.12 + pulse * 0.12 * fade

    draw_panel(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (1.0, 0.97, 0.80, alpha))

    # Central glow panels
    draw_panel(
        WINDOW_WIDTH / 2 - 330,
        WINDOW_HEIGHT / 2 - 120,
        660,
        210,
        (0.85, 0.20 + pulse * 0.20, 0.05, glow_alpha),
    )
    draw_panel(
        WINDOW_WIDTH / 2 - 285,
        WINDOW_HEIGHT / 2 - 95,
        570,
        160,
        (0.12, 0.02, 0.02, 0.35 + fade * 0.18),
    )

    text_scale = 0.28 + math.sin(progress * math.pi * 1.6) * 0.09
    text_center_x = WINDOW_WIDTH / 2
    text_y = WINDOW_HEIGHT / 2 + 15
    goal_text = "GOAL!!!!"
    goal_text_width = get_stroke_text_width(goal_text) * text_scale
    text_x = text_center_x - goal_text_width / 2

    draw_text(
        WINDOW_WIDTH / 2 - 92,
        WINDOW_HEIGHT / 2 + 88,
        "AMAZING FINISH!",
        GLUT_BITMAP_HELVETICA_18,
        (1.0, 0.97, 0.82),
    )

    # Deep shadow
    draw_stroke_text_2d(
        text_x + 11,
        text_y - 11,
        goal_text,
        scale=text_scale,
        color=(0.08, 0.01, 0.01),
        line_width=7.0,
    )

    # Outer glow layer
    draw_stroke_text_2d(
        text_x - 1,
        text_y + 1,
        goal_text,
        scale=text_scale * 1.01,
        color=(1.0, 0.45 + 0.25 * pulse, 0.05),
        line_width=8.5,
    )

    # Main celebratory text
    draw_stroke_text_2d(
        text_x,
        text_y,
        goal_text,
        scale=text_scale,
        color=(1.0, 0.86 + 0.08 * pulse, 0.08),
        line_width=5.8,
    )

    # Highlight pass
    draw_stroke_text_2d(
        text_x + 2,
        text_y + 2,
        goal_text,
        scale=text_scale,
        color=(1.0, 0.98, 0.90),
        line_width=2.2,
    )

    draw_text(
        WINDOW_WIDTH / 2 - 72,
        WINDOW_HEIGHT / 2 - 72,
        "Crowd goes wild!",
        GLUT_BITMAP_HELVETICA_18,
        (1.0, 0.93, 0.75),
    )
    
    end_2d()


# ============== DIFFICULTY SELECTION SCREEN ==============
def draw_difficulty_selection():
    """Draw the difficulty selection menu."""
    begin_2d()
    draw_panel(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (0.02, 0.03, 0.06, 0.7))
    draw_panel(WINDOW_WIDTH / 2 - 350, WINDOW_HEIGHT / 2 - 150, 700, 300, (0.03, 0.05, 0.10, 0.9))
    
    draw_text(WINDOW_WIDTH / 2 - 180, WINDOW_HEIGHT / 2 + 100, "SELECT DIFFICULTY", 
              GLUT_BITMAP_TIMES_ROMAN_24, (0.98, 0.95, 0.70))
    
    color_easy = (0.2, 1.0, 0.2) if current_difficulty == DIFFICULTY_EASY else (1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH / 2 - 200, WINDOW_HEIGHT / 2 + 30, "1 - EASY (Slower bots, easy steals)", 
              GLUT_BITMAP_HELVETICA_18, color_easy)
    
    color_medium = (1.0, 1.0, 0.2) if current_difficulty == DIFFICULTY_MEDIUM else (1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH / 2 - 200, WINDOW_HEIGHT / 2 - 10, "2 - MEDIUM (Balanced challenge)", 
              GLUT_BITMAP_HELVETICA_18, color_medium)
    
    color_hard = (1.0, 0.2, 0.2) if current_difficulty == DIFFICULTY_HARD else (1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH / 2 - 200, WINDOW_HEIGHT / 2 - 50, "3 - HARD (Faster bots, aggressive)", 
              GLUT_BITMAP_HELVETICA_18, color_hard)
    
    draw_text(WINDOW_WIDTH / 2 - 250, WINDOW_HEIGHT / 2 - 110, "Press ENTER to start with selected difficulty", 
              GLUT_BITMAP_HELVETICA_12, (0.90, 0.95, 1.0))
    
    end_2d()


def draw_hud():
    begin_2d()
    scoreboard_y = WINDOW_HEIGHT - 22
    left_x = WINDOW_WIDTH / 2 - 300
    center_x = WINDOW_WIDTH / 2 + 55
    left_box_center = (left_x + (center_x - 18)) / 2
    timer_box_center = (center_x + (center_x + 160)) / 2

    # Single team banner
    glColor3f(0.40, 0.06, 0.08)
    glBegin(GL_QUADS)
    glVertex2f(left_x, scoreboard_y - 40)
    glVertex2f(center_x - 18, scoreboard_y - 40)
    glVertex2f(center_x - 36, scoreboard_y)
    glVertex2f(left_x + 18, scoreboard_y)
    glEnd()
    glColor3f(0.78, 0.60, 0.22)
    glLineWidth(2.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(left_x, scoreboard_y - 40)
    glVertex2f(center_x - 18, scoreboard_y - 40)
    glVertex2f(center_x - 36, scoreboard_y)
    glVertex2f(left_x + 18, scoreboard_y)
    glEnd()

    # Timer box
    glColor3f(0.08, 0.07, 0.10)
    glBegin(GL_QUADS)
    glVertex2f(center_x, scoreboard_y - 44)
    glVertex2f(center_x + 160, scoreboard_y - 44)
    glVertex2f(center_x + 144, scoreboard_y)
    glVertex2f(center_x + 16, scoreboard_y)
    glEnd()
    glColor3f(0.93, 0.76, 0.25)
    glBegin(GL_LINE_LOOP)
    glVertex2f(center_x, scoreboard_y - 44)
    glVertex2f(center_x + 160, scoreboard_y - 44)
    glVertex2f(center_x + 144, scoreboard_y)
    glVertex2f(center_x + 16, scoreboard_y)
    glEnd()

    time_text = f"{max(0, int(math.ceil(match_time))):02d}"
    draw_text_centered(left_box_center - 40, scoreboard_y - 26, "BRACU", GLUT_BITMAP_HELVETICA_18, (1.0, 0.98, 0.95))
    draw_text_centered(left_box_center + 74, scoreboard_y - 26, f"{score}", GLUT_BITMAP_HELVETICA_18, (1.0, 0.96, 0.82))
    draw_text_centered(timer_box_center, scoreboard_y - 26, time_text, GLUT_BITMAP_HELVETICA_18, (1.0, 1.0, 1.0))

    # Minimal bottom info bar so the field stays visible like the reference
    draw_panel(18, 16, 470, 54, (0.03, 0.05, 0.10, 0.54))
    draw_text(30, 50, default_status(), font=GLUT_BITMAP_HELVETICA_12, color=(0.95, 0.97, 1.0))
    draw_text(30, 28, "W A S D move | SPACE shoot | C cheat | P weather | V camera | R reset", font=GLUT_BITMAP_HELVETICA_12, color=(0.82, 0.90, 1.0))

    cheat_text = "CHEAT ON" if cheat_mode else "CHEAT OFF"
    weather_text = ["SUNNY", "CLOUDY", "RAINY"][current_weather]
    draw_text(WINDOW_WIDTH - 215, 50, cheat_text, GLUT_BITMAP_HELVETICA_12, (0.95, 0.78, 0.28) if cheat_mode else (0.80, 0.86, 0.92))
    draw_text(WINDOW_WIDTH - 215, 28, weather_text, GLUT_BITMAP_HELVETICA_12, (0.88, 0.95, 1.0))
    
    end_2d()


def draw_menu_overlay(title, subtitle):
    begin_2d()
    draw_panel(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (0.02, 0.03, 0.06, 0.55))
    draw_panel(WINDOW_WIDTH / 2 - 300, WINDOW_HEIGHT / 2 - 110, 600, 220, (0.03, 0.05, 0.10, 0.82))
    draw_text(WINDOW_WIDTH / 2 - 145, WINDOW_HEIGHT / 2 + 46, title, GLUT_BITMAP_TIMES_ROMAN_24, (0.98, 0.95, 0.70))
    draw_text(WINDOW_WIDTH / 2 - 210, WINDOW_HEIGHT / 2 + 8, subtitle, GLUT_BITMAP_HELVETICA_18, (0.90, 0.95, 1.0))
    draw_text(WINDOW_WIDTH / 2 - 175, WINDOW_HEIGHT / 2 - 34, "W A S D: move the player", GLUT_BITMAP_HELVETICA_18, (1, 1, 1))
    draw_text(WINDOW_WIDTH / 2 - 175, WINDOW_HEIGHT / 2 - 64, "SPACE: shoot the ball toward goal", GLUT_BITMAP_HELVETICA_18, (1, 1, 1))
    draw_text(WINDOW_WIDTH / 2 - 175, WINDOW_HEIGHT / 2 - 94, "ENTER: start or restart match", GLUT_BITMAP_HELVETICA_18, (1, 1, 1))
    end_2d()


def draw_scene():
    draw_sky()
    draw_stadium()
    draw_field()
    draw_goal()
    
    draw_crowd()

    draw_shadow(player.x, player.z, 1.05)
    draw_human(player, is_player=True)

    for bot in bots:
        draw_shadow(bot.x, bot.z, 0.95)
        draw_human(bot, is_player=False)

    draw_shadow(ball.x, ball.z, 0.50)
    draw_ball()


# ============== CAMERA SETUP ==============
def setup_camera():
    """Setup camera based on current camera mode with universal rotation support."""
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    rad = math.radians(cam_orbit)

    if camera_mode == CAMERA_MODE_DEFAULT:
        # Side view with manual rotation around the center
        dist = 60.0
        gluLookAt(
            dist * math.sin(rad), 35.0, dist * math.cos(rad),
            0.0, 0.0, 0.0,
            0.0, 1.0, 0.0,
        )
    elif camera_mode == CAMERA_MODE_FIRST_PERSON:
        # First-person view with manual looking (cam_orbit as yaw offset)
        player_angle = math.atan2(player.facing_x, player.facing_z)
        total_rad = player_angle + rad
        
        look_x = player.x + math.sin(total_rad) * 20.0
        look_z = player.z + math.cos(total_rad) * 20.0
        
        # Move eye slightly forward from center to avoid head clipping
        eye_offset = 0.75
        eye_x = player.x + player.facing_x * eye_offset
        eye_z = player.z + player.facing_z * eye_offset
        eye_y = 3.3
        
        gluLookAt(
            eye_x, eye_y, eye_z,
            look_x, eye_y - 0.2, look_z,
            0.0, 1.0, 0.0,
        )
    elif camera_mode == CAMERA_MODE_THIRD_PERSON:
        # Orbital camera around the player controlled by arrow keys
        # Use a distance that scales slightly with height for better framing
        dist = 30.0 + (cam_h * 0.05) 
        
        cam_x = player.x + dist * math.sin(rad)
        cam_z = player.z + dist * math.cos(rad)
        cam_y = cam_h
        
        gluLookAt(
            cam_x, cam_y, cam_z,
            player.x, 1.5, player.z,
            0.0, 1.0, 0.0,
        )


def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    if game_state == GAME_STATE_DIFFICULTY_SELECT:
        setup_projection()
        draw_difficulty_selection()
        glutSwapBuffers()
        return
    
    setup_projection()
    setup_camera()
    
    draw_scene()
    draw_hud()
    draw_shot_power_bar()
    draw_goal_flash()

    if not game_started:
        draw_menu_overlay("3D Football Game", "A polished OpenGL university project")
    elif game_over:
        draw_menu_overlay("Full Time", f"Final Score: {score} goals")

    glutSwapBuffers()


def keep_inside_field(actor):
    actor.x = clamp(actor.x, -FIELD_WIDTH / 2 + actor.radius, FIELD_WIDTH / 2 - actor.radius)
    actor.z = clamp(actor.z, -FIELD_LENGTH / 2 + actor.radius, FIELD_LENGTH / 2 - actor.radius)


def lose_ball_to_defender(bot):
    global player_has_ball
    player_has_ball = False
    ball.x = bot.x
    ball.z = bot.z + 0.8
    clear_x = player.x - bot.x + random.uniform(-0.6, 0.6)
    clear_z = 18.0 + random.uniform(0.0, 4.0)
    clear_x, clear_z = normalize_2d(clear_x, clear_z)
    ball.vx = clear_x * 13.0
    ball.vz = clear_z * 13.0
    set_status("Defender stole the ball!", 1.1)


def update_player(dt):
    global cheat_mode
    move_x = 0.0
    move_z = 0.0

    if b'w' in keys_down or b'W' in keys_down:
        move_z -= 1.0
    if b's' in keys_down or b'S' in keys_down:
        move_z += 1.0
    if b'a' in keys_down or b'A' in keys_down:
        move_x -= 1.0
    if b'd' in keys_down or b'D' in keys_down:
        move_x += 1.0

    # Any manual movement input should immediately cancel cheat control,
    # so left/right movement works normally again.
    if cheat_mode and (move_x != 0.0 or move_z != 0.0):
        cheat_mode = False
        set_status("Cheat mode disabled: manual control restored", 1.2)

    if cheat_mode and game_started and not game_over and freeze_timer <= 0:
        update_cheat_player(dt)
        return

    move_x, move_z = normalize_2d(move_x, move_z)
    if move_x != 0.0 or move_z != 0.0:
        player.facing_x = move_x
        player.facing_z = move_z

    player.x += move_x * PLAYER_SPEED * dt
    player.z += move_z * PLAYER_SPEED * dt
    keep_inside_field(player)

    if player_has_ball:
        attach_ball_to_player()
    elif distance_2d(player.x, player.z, ball.x, ball.z) < 1.25 and abs(ball.vx) + abs(ball.vz) < 9.0:
        take_ball_control()


def get_cheat_press_target():
    """Pick a defender to press before winning the ball, instead of running directly to goal."""
    if not bots:
        return ball.x, ball.z

    closest_bot = min(bots, key=lambda bot: distance_2d(bot.x, bot.z, ball.x, ball.z))
    bot_ball_dist = distance_2d(closest_bot.x, closest_bot.z, ball.x, ball.z)

    # If a defender is effectively on or near the ball, press the defender first.
    if bot_ball_dist < 5.5:
        press_x = closest_bot.x - closest_bot.facing_x * 0.6
        press_z = closest_bot.z - closest_bot.facing_z * 0.6
        return press_x, press_z

    return ball.x, ball.z


def get_cheat_dribble_target():
    """Create a more realistic attack path with side dribbling before the final shot."""
    run_time = glutGet(GLUT_ELAPSED_TIME) * 0.001
    progress_to_goal = clamp((-player.z) / (FIELD_LENGTH / 2), 0.0, 1.0)

    # Base side-to-side dribble gets slightly tighter near the box.
    wave = math.sin(run_time * 3.2) * CHEAT_DRIBBLE_AMPLITUDE * (1.0 - progress_to_goal * 0.35)

    # Dodge away from the nearest outfield defender if one is closing the lane.
    dodge = 0.0
    outfield_bots = [bot for bot in bots if bot.role != "goalkeeper"]
    if outfield_bots:
        nearest_bot = min(outfield_bots, key=lambda bot: distance_2d(bot.x, bot.z, player.x, player.z))
        bot_dist = distance_2d(nearest_bot.x, nearest_bot.z, player.x, player.z)
        if bot_dist < 8.0 and nearest_bot.z < player.z + 6.0:
            if nearest_bot.x >= player.x:
                dodge = -CHEAT_DRIBBLE_DODGE
            else:
                dodge = CHEAT_DRIBBLE_DODGE

    target_x = clamp(wave + dodge, -FIELD_WIDTH / 2 + 2.5, FIELD_WIDTH / 2 - 2.5)

    # Straighten up a bit just before the shot so the finish still looks clean.
    if player.z <= CHEAT_FINISH_ZONE_Z + 7.0:
        target_x *= 0.35

    return target_x, CHEAT_FINISH_ZONE_Z


def update_cheat_player(dt):
    """Automatically control the player with defender pressing, tackling, and a real finish shot."""
    global cheat_mode
    move_x = 0.0
    move_z = 0.0

    if player_has_ball:
        # Carry the ball with lateral dribbling and defender dodging.
        target_x, target_z = get_cheat_dribble_target()
    else:
        target_x, target_z = get_cheat_press_target()

    move_x, move_z = normalize_2d(target_x - player.x, target_z - player.z)
    if move_x != 0.0 or move_z != 0.0:
        player.facing_x = move_x
        player.facing_z = move_z

    player.x += move_x * CHEAT_PLAYER_SPEED * dt
    player.z += move_z * CHEAT_PLAYER_SPEED * dt
    keep_inside_field(player)

    if player_has_ball:
        attach_ball_to_player()

        goal_dir_x, goal_dir_z = normalize_2d(-player.x, -FIELD_LENGTH / 2 - player.z)
        if goal_dir_x != 0.0 or goal_dir_z != 0.0:
            player.facing_x = goal_dir_x
            player.facing_z = goal_dir_z
            attach_ball_to_player()

        close_to_finish = (
            player.z <= CHEAT_FINISH_ZONE_Z
            and abs(player.x) <= GOAL_WIDTH / 2 - 1.2
        )
        if close_to_finish:
            perform_cheat_finish_shot()
            return
    else:
        # Prioritize physical recovery through tackles; only collect a truly loose ball directly.
        attempt_player_tackle()
        if distance_2d(player.x, player.z, ball.x, ball.z) < 1.10 and abs(ball.vx) + abs(ball.vz) < 4.5:
            take_ball_control()


def perform_cheat_finish_shot():
    """Take a visible high-quality shot instead of forcing an instant goal."""
    global player_has_ball, shots, shot_charging, shot_power

    if not player_has_ball:
        return

    goal_x = clamp(-player.x * 0.30 + random.uniform(-0.5, 0.5), -GOAL_WIDTH / 2 + 1.1, GOAL_WIDTH / 2 - 1.1)
    goal_z = -FIELD_LENGTH / 2
    aim_x, aim_z = normalize_2d(goal_x - ball.x, goal_z - ball.z)

    if aim_x == 0.0 and aim_z == 0.0:
        aim_x, aim_z = 0.0, -1.0

    player.facing_x = aim_x
    player.facing_z = aim_z

    player_has_ball = False
    shot_charging = False
    shot_power = 0.0
    ball.x = player.x + aim_x * 1.25
    ball.z = player.z + aim_z * 1.25
    ball.vx = aim_x * CHEAT_SHOT_POWER
    ball.vz = aim_z * CHEAT_SHOT_POWER
    shots += 1
    set_status("Cheat shot launched!", 0.9)


def attempt_player_tackle():
    """Let the player tackle nearby bots and win the ball back."""
    global tackle_cooldown

    if player_has_ball or tackle_cooldown > 0.0 or freeze_timer > 0.0:
        return

    for bot in bots:
        dist_pb = distance_2d(player.x, player.z, bot.x, bot.z)
        bot_near_ball = distance_2d(bot.x, bot.z, ball.x, ball.z) < 2.1
        player_near_ball = distance_2d(player.x, player.z, ball.x, ball.z) < 2.3

        if dist_pb <= TACKLE_RANGE and (bot_near_ball or player_near_ball):
            push_x, push_z = normalize_2d(bot.x - player.x, bot.z - player.z)
            if push_x == 0.0 and push_z == 0.0:
                push_x, push_z = 0.0, 1.0

            bot.x += push_x * 1.25
            bot.z += push_z * 1.25
            keep_inside_field(bot)

            ball.vx = push_x * TACKLE_PUSH * 0.25
            ball.vz = push_z * TACKLE_PUSH * 0.15
            tackle_cooldown = TACKLE_COOLDOWN
            take_ball_control()
            set_status("Strong tackle! Possession won back", 0.9)
            return


def update_bots(dt):
    target_x = ball.x if not player_has_ball else player.x
    target_z = ball.z if not player_has_ball else player.z
    match_time_now = glutGet(GLUT_ELAPSED_TIME) * 0.001

    ordered = sorted(
        range(len(bots)),
        key=lambda i: distance_2d(bots[i].x, bots[i].z, target_x, target_z)
    )

    if current_difficulty == DIFFICULTY_EASY:
        speed_mult = 0.6
    elif current_difficulty == DIFFICULTY_MEDIUM:
        speed_mult = 1.0
    else:
        speed_mult = 1.4

    for index, bot in enumerate(bots):
        press_rank = ordered.index(index)

        if bot.role == "goalkeeper":
            desired_x = clamp(target_x * 0.4, -GOAL_WIDTH / 2 + 1.3, GOAL_WIDTH / 2 - 1.3)
            desired_z = -FIELD_LENGTH / 2 + 2.0
            speed = GOALKEEPER_SPEED * speed_mult
        else:
            lane_wave = math.sin(match_time_now * 0.9 + bot.anim_seed) * 1.8
            home_bias_x = bot.home_x + lane_wave
            home_bias_z = bot.home_z + math.cos(match_time_now * 0.7 + bot.anim_seed) * 1.0

            if press_rank == 0:
                desired_x = target_x * 0.85 + bot.home_x * 0.15
                desired_z = target_z + (1.2 if player_has_ball else 0.2)
                speed = BOT_SPEED * 1.02 * speed_mult
            elif press_rank == 1:
                support_side = -1.0 if bot.home_x <= 0 else 1.0
                desired_x = clamp(target_x + support_side * 5.5, -FIELD_WIDTH / 2 + 2.0, FIELD_WIDTH / 2 - 2.0)
                desired_z = clamp(target_z + 3.5, -FIELD_LENGTH / 2 + 8.0, FIELD_LENGTH / 2 - 6.0)
                speed = BOT_SPEED * 0.90 * speed_mult
            elif bot.role == "defender":
                desired_x = clamp(home_bias_x * 0.75 + target_x * 0.25, -FIELD_WIDTH / 2 + 2.0, FIELD_WIDTH / 2 - 2.0)
                desired_z = clamp(bot.home_z + 0.20 * (target_z - bot.home_z), -24.0, -8.0)
                speed = BOT_SPEED * 0.72 * speed_mult
            elif bot.role == "midfielder":
                support_side = -1.0 if bot.home_x <= 0 else 1.0
                desired_x = clamp(home_bias_x * 0.55 + target_x * 0.45 + support_side * 1.6, -FIELD_WIDTH / 2 + 2.0, FIELD_WIDTH / 2 - 2.0)
                desired_z = clamp(bot.home_z + 0.45 * (target_z - bot.home_z), -12.0, 10.0)
                speed = BOT_SPEED * 0.82 * speed_mult
            else:
                desired_x = home_bias_x
                desired_z = home_bias_z
                speed = BOT_SPEED * 0.62 * speed_mult

            # Keep teammates from sticking together by adding local repulsion.
            repel_x = 0.0
            repel_z = 0.0
            for other in bots:
                if other is bot:
                    continue
                dx = bot.x - other.x
                dz = bot.z - other.z
                dist = math.sqrt(dx * dx + dz * dz)
                if 0.001 < dist < 5.0:
                    strength = (5.0 - dist) / 5.0
                    repel_x += (dx / dist) * strength * 2.8
                    repel_z += (dz / dist) * strength * 2.2

            desired_x = clamp(desired_x + repel_x, -FIELD_WIDTH / 2 + 2.0, FIELD_WIDTH / 2 - 2.0)
            desired_z = clamp(desired_z + repel_z, -FIELD_LENGTH / 2 + 2.0, FIELD_LENGTH / 2 - 2.0)

        dir_x, dir_z = normalize_2d(desired_x - bot.x, desired_z - bot.z)
        if dir_x != 0.0 or dir_z != 0.0:
            bot.facing_x = dir_x
            bot.facing_z = dir_z

        bot.x += dir_x * speed * dt
        bot.z += dir_z * speed * dt
        keep_inside_field(bot)

        steal_range = STEAL_RADIUS
        if current_difficulty == DIFFICULTY_EASY:
            steal_range *= 0.7
        elif current_difficulty == DIFFICULTY_HARD:
            steal_range *= 1.3

        if player_has_ball and distance_2d(bot.x, bot.z, player.x, player.z) < steal_range:
            lose_ball_to_defender(bot)


def resolve_actor_collisions():
    actors = [player] + bots
    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            a = actors[i]
            b = actors[j]
            dx = b.x - a.x
            dz = b.z - a.z
            dist = math.sqrt(dx * dx + dz * dz)
            min_dist = a.radius + b.radius

            if dist == 0:
                dx, dz, dist = 0.01, 0.01, 0.014
            if dist < min_dist:
                nx, nz = dx / dist, dz / dist
                overlap = min_dist - dist

                # Give the user-controlled player movement priority so
                # left/right chasing still feels responsive without the ball.
                if a.role == "player" and b.role != "player":
                    a_push = overlap * 0.20
                    b_push = overlap * 0.80
                elif b.role == "player" and a.role != "player":
                    a_push = overlap * 0.80
                    b_push = overlap * 0.20
                else:
                    a_push = overlap * 0.50
                    b_push = overlap * 0.50

                a.x -= nx * a_push
                a.z -= nz * a_push
                b.x += nx * b_push
                b.z += nz * b_push
                keep_inside_field(a)
                keep_inside_field(b)


def resolve_ball_collisions():
    if player_has_ball:
        return

    actors = [player] + bots
    for actor in actors:
        dx = ball.x - actor.x
        dz = ball.z - actor.z
        dist = math.sqrt(dx * dx + dz * dz)
        min_dist = actor.radius + BALL_RADIUS

        if dist == 0:
            dx, dz, dist = 0.01, 0.01, 0.014

        if dist < min_dist:
            nx, nz = dx / dist, dz / dist
            push = min_dist - dist
            ball.x += nx * push
            ball.z += nz * push
            impulse = 6.0 if actor.role == "player" else 9.0
            ball.vx += nx * impulse
            ball.vz += nz * impulse
            if actor.role != "player":
                set_status("Shot blocked by defender!", 0.8)


def update_ball(dt):
    global player_has_ball

    if player_has_ball:
        attach_ball_to_player()
        return

    ball.x += ball.vx * dt
    ball.z += ball.vz * dt

    damping = BALL_FRICTION ** (dt * 60.0)
    ball.vx *= damping
    ball.vz *= damping

    if abs(ball.vx) < 0.12:
        ball.vx = 0.0
    if abs(ball.vz) < 0.12:
        ball.vz = 0.0

    half_w = FIELD_WIDTH / 2 - BALL_RADIUS
    half_l = FIELD_LENGTH / 2 - BALL_RADIUS

    if ball.x < -half_w:
        ball.x = -half_w
        ball.vx *= -0.78
    if ball.x > half_w:
        ball.x = half_w
        ball.vx *= -0.78
    if ball.z > half_l:
        ball.z = half_l
        ball.vz *= -0.78

    goal_half = GOAL_WIDTH / 2
    goal_line = -FIELD_LENGTH / 2
    if ball.z <= goal_line:
        if ball_is_goal():
            handle_goal()
            return
        ball.z = goal_line + BALL_RADIUS * 0.65
        ball.vz = abs(ball.vz) * 0.78
        if abs(abs(ball.x) - goal_half) < 1.15:
            ball.vx *= -0.92
            set_status("Hit the post!", 0.9)
        else:
            set_status("Shot missed the goal", 0.9)

    if not player_has_ball and distance_2d(player.x, player.z, ball.x, ball.z) < 1.10 and abs(ball.vx) + abs(ball.vz) < 8.0:
        take_ball_control()


def handle_goal():
    global score, freeze_timer, celebrating, celebration_timer, goal_flash, goal_flash_timer, cheat_mode
    score += 1
    cheat_mode = False
    freeze_timer = 1.4
    celebrating = True
    celebration_timer = CELEBRATION_DURATION
    goal_flash = True
    goal_flash_timer = GOAL_FLASH_DURATION
    set_status("Goal! Excellent finish!", 1.4)
    reset_positions(full_reset=False)


def kick_ball():
    global player_has_ball, shots, shot_charging, shot_power

    if not game_started or game_over or freeze_timer > 0:
        return

    if not player_has_ball:
        set_status("Recover the ball before shooting", 1.0)
        return

    goal_x = clamp(random.uniform(-2.5, 2.5), -GOAL_WIDTH / 2 + 1.2, GOAL_WIDTH / 2 - 1.2)
    goal_z = -FIELD_LENGTH / 2
    aim_x, aim_z = normalize_2d(goal_x - ball.x, goal_z - ball.z)

    player_has_ball = False
    ball.x = player.x + aim_x * 1.2
    ball.z = player.z + aim_z * 1.2

    distance_boost = clamp((player.z + FIELD_LENGTH / 2) / FIELD_LENGTH, 0.3, 1.0)
    
    if shot_power > 0.0:
        power = KICK_POWER * (0.4 + shot_power * 0.6) * (0.75 + distance_boost * 0.4)
        shot_power = 0.0
        shot_charging = False
    else:
        power = KICK_POWER * (0.75 + distance_boost * 0.4)
    
    ball.vx = aim_x * power
    ball.vz = aim_z * power
    shots += 1
    set_status("Power shot taken!", 0.8)


def take_ball_control():
    global player_has_ball
    player_has_ball = True
    attach_ball_to_player()
    set_status("Possession recovered", 0.7)


def update_match(dt):
    global match_time, game_over, status_timer, freeze_timer, shot_charging, shot_power, tackle_cooldown
    global celebrating, celebration_timer, goal_flash, goal_flash_timer

    if status_timer > 0:
        status_timer = max(0.0, status_timer - dt)
    if tackle_cooldown > 0:
        tackle_cooldown = max(0.0, tackle_cooldown - dt)

    if not game_started or game_over:
        return

    if freeze_timer > 0:
        freeze_timer = max(0.0, freeze_timer - dt)
        return

    if celebrating:
        celebration_timer = max(0.0, celebration_timer - dt)
        if celebration_timer <= 0:
            celebrating = False

    if goal_flash:
        goal_flash_timer = max(0.0, goal_flash_timer - dt)
        if goal_flash_timer <= 0:
            goal_flash = False

    if shot_charging:
        shot_power = min(shot_power + dt / max_charge_time, 1.0)

    match_time = max(0.0, match_time - dt)
    if match_time <= 0.0:
        game_over = True
        set_status(f"Full time. Final score: {score}", 4.0)
        return

    update_player(dt)
    update_bots(dt)
    attempt_player_tackle()
    resolve_actor_collisions()
    resolve_ball_collisions()
    update_ball(dt)


def timer(value):
    global last_time_ms

    current = glutGet(GLUT_ELAPSED_TIME)
    if last_time_ms == 0:
        last_time_ms = current

    dt = (current - last_time_ms) / 1000.0
    dt = clamp(dt, 0.0, 0.03)
    last_time_ms = current

    update_match(dt)
    glutPostRedisplay()
    glutTimerFunc(16, timer, 0)


def specialKeyListener(key, x, y):
    """Handle special keys (arrow keys) for camera control in third-person mode.
    Arrow keys allow the player to rotate the camera around the arena."""
    global cam_orbit, cam_h

    # UP arrow: Raise camera height
    if key == GLUT_KEY_UP:
        cam_h = min(cam_h + 25, 1400)              # Increase height, capped at 1400
    # DOWN arrow: Lower camera height
    elif key == GLUT_KEY_DOWN:
        cam_h = max(cam_h - 25, 60)                # Decrease height, minimum 60
    # LEFT arrow: Rotate camera counter-clockwise around player
    elif key == GLUT_KEY_LEFT:
        cam_orbit = (cam_orbit - 3) % 360          # Decrease orbit angle
    # RIGHT arrow: Rotate camera clockwise around player
    elif key == GLUT_KEY_RIGHT:
        cam_orbit = (cam_orbit + 3) % 360          # Increase orbit angle

    glutPostRedisplay()                            # Request screen redraw


def keyboard_down(key, x, y):
    global game_state, current_difficulty, game_started, game_over, shot_charging, camera_mode, current_weather, cheat_mode
    
    keys_down.add(key)

    if game_state == GAME_STATE_DIFFICULTY_SELECT:
        if key == b'1':
            current_difficulty = DIFFICULTY_EASY
        elif key == b'2':
            current_difficulty = DIFFICULTY_MEDIUM
        elif key == b'3':
            current_difficulty = DIFFICULTY_HARD
        elif key in (b'\r', b'\n'):
            current_weather = random.randint(0, 2)
            start_new_match()
        elif key == b'\x1b':
            raise SystemExit
        return

    if key in (b'\r', b'\n'):
        if not game_started or game_over:
            start_new_match()
    elif key == b' ':
        if player_has_ball and game_started and not game_over:
            shot_charging = True
    elif key in (b'c', b'C'):
        cheat_mode = not cheat_mode
        shot_charging = False
        if cheat_mode:
            set_status("Cheat mode enabled: auto attack started", 1.6)
        else:
            set_status("Cheat mode disabled", 1.2)
    elif key in (b'p', b'P'):
        current_weather = (current_weather + 1) % 3
        set_status(f"Weather changed to {['Sunny', 'Cloudy', 'Rainy'][current_weather]}", 1.1)
    elif key in (b'r', b'R'):
        game_state = GAME_STATE_DIFFICULTY_SELECT
        game_started = False
        game_over = False
    elif key in (b'v', b'V'):
        camera_mode = (camera_mode + 1) % 3
    elif key in (b'0', b'1', b'2', b'3'):
        if key == b'0':
            camera_mode = CAMERA_MODE_DEFAULT
        elif key == b'1':
            camera_mode = CAMERA_MODE_FIRST_PERSON
        elif key == b'2':
            camera_mode = CAMERA_MODE_THIRD_PERSON
    elif key == b'\x1b':
        raise SystemExit


def keyboard_up(key, x, y):
    global shot_charging
    
    if key in keys_down:
        keys_down.remove(key)
    
    if key == b' ':
        if shot_charging:
            kick_ball()
            shot_charging = False


def reshape(width, height):
    global WINDOW_WIDTH, WINDOW_HEIGHT
    WINDOW_WIDTH = max(1, width)
    WINDOW_HEIGHT = max(1, height)
    setup_projection()


def main():
    reset_positions(full_reset=True)

    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutInitWindowPosition(80, 50)
    glutCreateWindow(b"KICKBUZZ")

    setup_graphics()
    setup_projection()

    glutDisplayFunc(display)
    glutSpecialFunc(specialKeyListener)
    glutKeyboardFunc(keyboard_down)
    glutKeyboardUpFunc(keyboard_up)
    glutReshapeFunc(reshape)
    glutTimerFunc(16, timer, 0)
    glutMainLoop()


if __name__ == "__main__":
    main()
