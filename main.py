import json
import math
import os
import random
import sys
from collections import deque

import pygame
import pymunk

# ====================== BRANDING / GAME SETTINGS ======================
BRAND_NAME = "NEXUS"
BRAND_TAGLINE = "ARCADE EDITION"
GAME_TITLE = "NEXUS PINBALL"
GAME_ID = "nexus-pinball-arcade"
TOTAL_LEVELS = 100

pygame.init()
W, H = 600, 900

desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
SCALE = min(1.0, (desk_h - 110) / H)
WIN_W, WIN_H = int(W * SCALE), int(H * SCALE)
window = pygame.display.set_mode((WIN_W, WIN_H))
pygame.display.set_caption(GAME_TITLE)
canvas = pygame.Surface((W, H))
clock = pygame.time.Clock()

# Fonts
f_small = pygame.font.SysFont("arial", 18, bold=True)
f_med = pygame.font.SysFont("arial", 26, bold=True)
f_big = pygame.font.SysFont("arial", 52, bold=True)
f_huge = pygame.font.SysFont("arial", 80, bold=True)

# ------------------ Save file ------------------
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_pinball_save.json")
default_save = {"coins": 0, "owned": [0], "equipped": 0, "best": 0, "highest_level": 1}
save = default_save.copy()


def load_save():
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                save.update(data)
    except Exception:
        pass


def write_save():
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(save, f)
    except Exception:
        pass


load_save()

# ---------- Ball skins ----------
SKINS = [
    ("Classic", (255, 255, 255), (90, 90, 160), 0),
    ("Fire", (255, 150, 40), (160, 40, 0), 20),
    ("Ice", (150, 235, 255), (0, 90, 150), 50),
    ("Toxic", (130, 255, 90), (20, 120, 20), 90),
    ("Gold", (255, 215, 0), (150, 100, 0), 150),
    ("Galaxy", (210, 130, 255), (100, 20, 150), 250),
]

# ---------- Colours ----------
WALL = (255, 70, 210)
WALL_GLOW = (80, 10, 70)
CYAN = (0, 230, 255)
GOLD = (255, 215, 0)
RED = (255, 80, 110)

bg = pygame.Surface((W, H))
for y in range(H):
    t = y / H
    pygame.draw.line(bg, (int(12 + 22 * t), int(4 + 6 * t), int(36 + 44 * t)), (0, y), (W, y))
_rng = random.Random(7)
for _ in range(80):
    pygame.draw.circle(bg, (110, 110, 210), (_rng.randint(0, W), _rng.randint(0, H)), _rng.choice([1, 1, 2]))

# ====================== PHYSICS TABLE ======================
space = pymunk.Space()
space.gravity = (0, 900)
static = space.static_body
lines = []


def add_wall(a, b, elasticity=0.6):
    s = pymunk.Segment(static, a, b, 4)
    s.elasticity = elasticity
    s.friction = 0.3
    space.add(s)
    lines.append((a, b))


cx, cy, rad = 305, 300, 285
arc = []
for i in range(25):
    ang = math.pi + i * math.pi / 24
    arc.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
for a, b in zip(arc, arc[1:]):
    add_wall(a, b)

add_wall((20, 300), (20, 690))
add_wall((590, 300), (590, 900))
add_wall((545, 330), (545, 900))
add_wall((545, 900), (590, 900))
add_wall((20, 690), (210, 790))
add_wall((545, 690), (390, 790))

triangles = [
    [(60, 560), (60, 660), (150, 730)],
    [(505, 560), (505, 660), (415, 730)],
]
for pts in triangles:
    p = pymunk.Poly(static, pts)
    p.elasticity = 1.3
    p.friction = 0.2
    space.add(p)

bumpers = [(180, 280, 28), (380, 260, 28), (280, 410, 32)]
bumper_flash = [0, 0, 0]
for bx, by, br in bumpers:
    c = pymunk.Circle(static, br, (bx, by))
    c.elasticity = 0.3
    space.add(c)


def make_flipper(pivot, length, rest, active):
    body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    body.position = pivot
    body.angle = rest
    shape = pymunk.Segment(body, (0, 0), (length, 0), 8)
    shape.elasticity = 0.5
    shape.friction = 0.9
    space.add(body, shape)
    return {"body": body, "length": length, "rest": rest, "active": active}


left_flip = make_flipper((210, 790), 85, 0.5, -0.5)
right_flip = make_flipper((390, 790), -85, -0.5, 0.5)


def move_flipper(f, pressed):
    body = f["body"]
    target = f["active"] if pressed else f["rest"]
    step = max(-0.35, min(0.35, target - body.angle))
    body.angular_velocity = step * 60


# ====================== BALL ======================
ball = None
ball_shape = None
trail = deque(maxlen=14)


def limit_velocity(body, gravity, damping, dt):
    pymunk.Body.update_velocity(body, gravity, damping, dt)
    v = body.velocity
    sp = math.hypot(v.x, v.y)
    if sp > 2200:
        body.velocity = (v.x * 2200 / sp, v.y * 2200 / sp)


def new_ball():
    global ball, ball_shape
    ball = pymunk.Body(1, pymunk.moment_for_circle(1, 0, 10))
    ball.position = (567, 860)
    ball.velocity_func = limit_velocity
    ball_shape = pymunk.Circle(ball, 10)
    ball_shape.elasticity = 0.5
    ball_shape.friction = 0.4
    space.add(ball, ball_shape)
    trail.clear()


def remove_ball():
    global ball, ball_shape
    if ball is not None:
        space.remove(ball, ball_shape)
        ball = None
        ball_shape = None


# ====================== COINS ======================
coin_positions = [(100, 380), (300, 150), (460, 400), (150, 520), (430, 520), (280, 600)]
coins = [{"x": x, "y": y, "alive": True} for x, y in coin_positions]
coin_respawn_timer = 0.0

# ====================== GAME VARS ======================
state = "splash"
state_time = 0.0
credit = 0
score = 0
lives = 3
run_coins = 0
shop_index = 0
shop_msg = ""
shop_msg_t = 0.0
menu_msg_t = 0.0
bonus_text_t = 0.0
current_level = 1
level_banner_timer = 0.0
menu_hint_timer = 0.0

mouse_left = False
mouse_right = False
mouse_launch = False


def set_state(s):
    global state, state_time
    state = s
    state_time = 0.0


def prepare_level(level_number):
    global current_level, coin_respawn_timer, bonus_text_t, level_banner_timer
    current_level = max(1, min(int(level_number), TOTAL_LEVELS))
    space.gravity = (0, 900 + (current_level - 1) * 22)
    remove_ball()
    new_ball()
    for c in coins:
        c["alive"] = True
    coin_respawn_timer = 0.0
    bonus_text_t = 0.0
    level_banner_timer = 1.6


def start_game():
    global score, lives, run_coins, current_level
    score = 0
    lives = 3
    run_coins = 0
    current_level = 1
    prepare_level(1)
    set_state("play")


# ====================== DRAW HELPERS ======================
def text(s, font, color, center=None, topleft=None, topright=None, alpha=255):
    img = font.render(s, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    r = img.get_rect()
    if center:
        r.center = center
    elif topleft:
        r.topleft = topleft
    elif topright:
        r.topright = topright
    canvas.blit(img, r)


def draw_glow_line(a, b):
    pygame.draw.line(canvas, WALL_GLOW, a, b, 12)
    pygame.draw.line(canvas, WALL, a, b, 3)


def draw_ball(pos, skin_idx, radius=10):
    _, main, glow, _ = SKINS[skin_idx]
    x, y = int(pos[0]), int(pos[1])
    pygame.draw.circle(canvas, glow, (x, y), radius + 7)
    pygame.draw.circle(canvas, main, (x, y), radius)
    pygame.draw.circle(canvas, (255, 255, 255), (x - radius // 3, y - radius // 3), max(2, radius // 4))


def draw_scene(t):
    canvas.blit(bg, (0, 0))
    for a, b in lines:
        draw_glow_line(a, b)

    for pts in triangles:
        pygame.draw.polygon(canvas, (60, 20, 140), pts)
        pygame.draw.polygon(canvas, CYAN, pts, 3)

    for i, (bx, by, br) in enumerate(bumpers):
        flash = bumper_flash[i] > 0
        pygame.draw.circle(canvas, (70, 10, 90), (bx, by), br + 9)
        pygame.draw.circle(canvas, (255, 255, 255) if flash else (255, 190, 40), (bx, by), br, 5)
        pygame.draw.circle(canvas, (255, 120, 30) if flash else (120, 30, 160), (bx, by), br - 8)
        if flash:
            bumper_flash[i] -= 1

    for i, c in enumerate(coins):
        if c["alive"]:
            w = max(4, abs(math.cos(t * 3 + i)) * 26)
            pygame.draw.ellipse(canvas, (150, 100, 0), (c["x"] - w / 2 - 2, c["y"] - 15, w + 4, 30))
            pygame.draw.ellipse(canvas, GOLD, (c["x"] - w / 2, c["y"] - 13, w, 26))

    for f in (left_flip, right_flip):
        pv = f["body"].position
        tip = f["body"].local_to_world((f["length"], 0))
        draw_glow_line((pv.x, pv.y), (tip.x, tip.y))
        pygame.draw.line(canvas, (255, 255, 255), (pv.x, pv.y), (tip.x, tip.y), 9)
        pygame.draw.circle(canvas, WALL, (int(pv.x), int(pv.y)), 8)

    if ball is not None:
        skin = save["equipped"]
        for i, (x, y) in enumerate(trail):
            r = int(2 + 7 * i / max(1, len(trail)))
            pygame.draw.circle(canvas, SKINS[skin][2], (int(x), int(y)), r)
        draw_ball((ball.position.x, ball.position.y), skin)

    # launch button for mobile
    btn_x = W - 90
    btn_y = H - 90
    pygame.draw.circle(canvas, (30, 40, 80), (btn_x, btn_y), 42)
    pygame.draw.circle(canvas, GOLD, (btn_x, btn_y), 32)
    text("GO", f_small, (20, 20, 20), center=(btn_x, btn_y))


def draw_hud():
    text(f"LEVEL {current_level}/{TOTAL_LEVELS}", f_med, CYAN, topleft=(28, 12))
    text(f"SCORE  {score}", f_med, (255, 255, 255), topleft=(28, 44))
    text(f"BEST  {max(save['best'], score)}", f_small, (170, 170, 230), topleft=(28, 76))
    text(f"COINS  {save['coins']}", f_med, GOLD, topright=(W - 28, 12))
    for i in range(lives):
        draw_ball((W - 40 - i * 26, 62), save["equipped"], 6)


# ====================== PRESENT ======================
def present():
    if SCALE < 1.0:
        window.blit(pygame.transform.smoothscale(canvas, (WIN_W, WIN_H)), (0, 0))
    else:
        window.blit(canvas, (0, 0))
    pygame.display.flip()


# ====================== MAIN LOOP ======================
while True:
    dt = min(clock.tick(60) / 1000, 0.05)
    state_time += dt
    now = pygame.time.get_ticks() / 1000

    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            write_save()
            pygame.quit()
            sys.exit()

        if ev.type == pygame.MOUSEBUTTONDOWN:
            x, y = ev.pos
            if x < W / 2:
                mouse_left = True
            if x >= W / 2:
                mouse_right = True
            if x > W - 120 and y > H - 120:
                mouse_launch = True

        if ev.type == pygame.MOUSEBUTTONUP:
            mouse_left = False
            mouse_right = False
            mouse_launch = False

        if ev.type == pygame.FINGERDOWN:
            x = ev.x * W
            y = ev.y * H
            if x < W / 2:
                mouse_left = True
            if x >= W / 2:
                mouse_right = True
            if x > W - 120 and y > H - 120:
                mouse_launch = True

        if ev.type == pygame.FINGERUP:
            mouse_left = False
            mouse_right = False
            mouse_launch = False

        if ev.type != pygame.KEYDOWN:
            continue
        k = ev.key

        if state in ("splash", "loading") and k in (pygame.K_SPACE, pygame.K_RETURN):
            set_state("loading" if state == "splash" else "menu")

        elif state == "menu":
            if k == pygame.K_ESCAPE:
                write_save()
                pygame.quit()
                sys.exit()
            elif k == pygame.K_c:
                credit = 1
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                if credit > 0:
                    credit = 0
                    start_game()
                else:
                    menu_msg_t = 1.5
            elif k == pygame.K_s:
                shop_index = save["equipped"]
                shop_msg = ""
                set_state("shop")

        elif state == "shop":
            if k == pygame.K_ESCAPE:
                write_save()
                set_state("menu")
            elif k in (pygame.K_RIGHT, pygame.K_d):
                shop_index = (shop_index + 1) % len(SKINS)
                shop_msg = ""
            elif k in (pygame.K_LEFT, pygame.K_a):
                shop_index = (shop_index - 1) % len(SKINS)
                shop_msg = ""
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                name, _, _, price = SKINS[shop_index]
                if shop_index in save["owned"]:
                    save["equipped"] = shop_index
                    shop_msg = f"{name} equipped!"
                elif save["coins"] >= price:
                    save["coins"] -= price
                    save["owned"].append(shop_index)
                    save["equipped"] = shop_index
                    shop_msg = f"{name} unlocked!"
                else:
                    shop_msg = f"Not enough coins! Need {price - save['coins']} more."
                shop_msg_t = 2.0
                write_save()

        elif state == "play":
            if k == pygame.K_ESCAPE:
                remove_ball()
                write_save()
                set_state("menu")
            elif k == pygame.K_SPACE and ball is not None:
                if ball.position.x > 545 and ball.position.y > 700:
                    ball.velocity = (0, -1500)

        elif state == "gameover":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                set_state("menu")

        elif state == "victory":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                set_state("menu")

    # ====================== STATES ======================
    if state == "splash":
        canvas.fill((0, 0, 0))
        a = int(255 * max(0, min(1, state_time / 0.8, (3.0 - state_time) / 0.8)))
        pygame.draw.circle(canvas, (255, 255, 255), (W // 2, 330), 46, 4)
        pygame.draw.circle(canvas, (255, 255, 255), (W // 2 + 26, 330), 46, 4)
        text(BRAND_NAME, f_big, (255, 255, 255), center=(W // 2, 450), alpha=a)
        text(BRAND_TAGLINE, f_small, (160, 160, 160), center=(W // 2, 505), alpha=a)
        if state_time >= 3.0:
            set_state("loading")

    elif state == "loading":
        canvas.blit(bg, (0, 0))
        text(GAME_TITLE, f_big, CYAN, center=(W // 2, 300))
        prog = min(1.0, state_time / 3.5)
        prog = prog * prog * (3 - 2 * prog)
        pygame.draw.rect(canvas, (40, 40, 90), (100, 480, 400, 24), border_radius=12)
        pygame.draw.rect(canvas, WALL, (100, 480, int(400 * prog), 24), border_radius=12)
        text(f"Loading...  {int(prog * 100)}%", f_med, (255, 255, 255), center=(W // 2, 540))
        tips = [
            "Collect coins to unlock new skins!",
            "Use both flippers at the right time!",
            "Advance through all 100 levels!",
        ]
        text("Tip: " + tips[int(state_time) % len(tips)], f_small, (170, 170, 230), center=(W // 2, 600))
        if state_time >= 3.5:
            set_state("menu")

    elif state == "menu":
        canvas.blit(bg, (0, 0))
        pulse = 0.5 + 0.5 * math.sin(now * 3)
        text(GAME_TITLE, f_big, (int(200 + 55 * pulse), 70, 210), center=(W // 2, 220))
        text("PRIVACY-FIRST ARCADE", f_small, (170, 170, 230), center=(W // 2, 275))
        draw_ball((W // 2, 380 + math.sin(now * 2) * 12), save["equipped"], 22)
        if credit == 0:
            if int(now * 2) % 2 == 0:
                text("START GAME", f_big, GOLD, center=(W // 2, 520))
            text("PRESS ENTER", f_med, (255, 255, 255), center=(W // 2, 580))
        else:
            text("CREDIT: 1", f_med, GOLD, center=(W // 2, 500))
            if int(now * 3) % 2 == 0:
                text("PRESS ENTER TO START", f_med, (255, 255, 255), center=(W // 2, 560))

        if menu_msg_t > 0:
            menu_msg_t -= dt
            text("Insert a coin first! (or press Enter)", f_small, (255, 100, 100), center=(W // 2, 630))
        text(f"COINS: {save['coins']}    BEST: {save['best']}", f_small, GOLD, center=(W // 2, 730))
        text(f"S - Ball Shop        ESC - Quit        ID: {GAME_ID}", f_small, (170, 170, 230), center=(W // 2, 780))

    elif state == "shop":
        canvas.blit(bg, (0, 0))
        name, main, glow, price = SKINS[shop_index]
        text("BALL SHOP", f_big, CYAN, center=(W // 2, 120))
        text(f"COINS: {save['coins']}", f_med, GOLD, center=(W // 2, 190))
        pygame.draw.circle(canvas, glow, (W // 2, 380), 90)
        pygame.draw.circle(canvas, main, (W // 2, 380), 62)
        pygame.draw.circle(canvas, (255, 255, 255), (W // 2 - 20, 360), 14)
        text("<", f_big, (255, 255, 255), center=(110, 380))
        text(">", f_big, (255, 255, 255), center=(W - 110, 380))
        text(name, f_big, (255, 255, 255), center=(W // 2, 520))
        if save["equipped"] == shop_index:
            status, col = "EQUIPPED", (120, 255, 120)
        elif shop_index in save["owned"]:
            status, col = "OWNED - press ENTER to equip", (120, 220, 255)
        else:
            status, col = f"LOCKED - {price} coins - press ENTER to buy", GOLD
        text(status, f_small, col, center=(W // 2, 580))
        for i in range(len(SKINS)):
            pygame.draw.circle(canvas, (255, 255, 255) if i == shop_index else (80, 80, 130), (W // 2 - 50 + i * 20, 650), 6)
        if shop_msg_t > 0:
            shop_msg_t -= dt
            text(shop_msg, f_small, (255, 255, 255), center=(W // 2, 710))
        text("LEFT / RIGHT - browse        ESC - back", f_small, (170, 170, 230), center=(W // 2, 800))

    elif state in ("play", "gameover", "victory"):
        if state == "play":
            keys = pygame.key.get_pressed()
            left_pressed = keys[pygame.K_LEFT] or keys[pygame.K_a] or mouse_left
            right_pressed = keys[pygame.K_RIGHT] or keys[pygame.K_d] or mouse_right
            move_flipper(left_flip, left_pressed)
            move_flipper(right_flip, right_pressed)

            # launch button for mobile / mouse
            if mouse_launch and ball is not None and ball.position.x > 545 and ball.position.y > 700:
                ball.velocity = (0, -1500)

            for _ in range(4):
                space.step(1 / 240)

            if ball is not None:
                bp = ball.position
                trail.append((bp.x, bp.y))

                for i, (bx, by, br) in enumerate(bumpers):
                    dx, dy = bp.x - bx, bp.y - by
                    dist = math.hypot(dx, dy)
                    if dist < br + 13 and bumper_flash[i] == 0:
                        n = (dx / dist, dy / dist) if dist else (0, -1)
                        boost = 650 + current_level * 18
                        ball.velocity = (n[0] * boost, n[1] * boost)
                        score += 100
                        bumper_flash[i] = 8

                for c in coins:
                    if c["alive"] and math.hypot(bp.x - c["x"], bp.y - c["y"]) < 24:
                        c["alive"] = False
                        save["coins"] += 1
                        run_coins += 1
                        score += 50

                if not any(c["alive"] for c in coins):
                    coin_respawn_timer += dt
                    if coin_respawn_timer > 1.25:
                        if current_level >= TOTAL_LEVELS:
                            save["best"] = max(save["best"], score)
                            save["highest_level"] = TOTAL_LEVELS
                            write_save()
                            set_state("victory")
                        else:
                            score += 1000 + current_level * 250
                            current_level += 1
                            save["highest_level"] = max(save.get("highest_level", 1), current_level)
                            write_save()
                            prepare_level(current_level)
                            bonus_text_t = 1.5
                            # keep score from previous level

                if bp.y > 940:
                    lives -= 1
                    remove_ball()
                    if lives > 0:
                        new_ball()
                    else:
                        save["best"] = max(save["best"], score)
                        save["highest_level"] = max(save.get("highest_level", 1), current_level)
                        write_save()
                        set_state("gameover")

        draw_scene(now)
        draw_hud()

        if state == "play" and ball is not None:
            if ball.position.x > 545 and ball.position.y > 700 and int(now * 2) % 2 == 0:
                text("PRESS SPACE OR TAP GO", f_small, (255, 255, 255), center=(300, 520))
            if bonus_text_t > 0:
                bonus_text_t -= dt
                text(f"LEVEL {current_level}! +{1000 + current_level * 250}", f_med, GOLD, center=(300, 470))
            text("A / D or arrows = flippers", f_small, (150, 150, 210), center=(300, 880))

        if state == "gameover":
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            canvas.blit(overlay, (0, 0))
            text("GAME OVER", f_huge, RED, center=(W // 2, 340))
            text(f"Score: {score}", f_med, (255, 255, 255), center=(W // 2, 440))
            text(f"Coins collected: {run_coins}", f_med, GOLD, center=(W // 2, 485))
            text(f"Total coins: {save['coins']}", f_small, GOLD, center=(W // 2, 525))
            if int(now * 2) % 2 == 0:
                text("Press ENTER", f_med, (255, 255, 255), center=(W // 2, 600))

        if state == "victory":
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            canvas.blit(overlay, (0, 0))
            text("YOU WIN!", f_huge, (120, 255, 120), center=(W // 2, 330))
            text(f"Final Score: {score}", f_med, (255, 255, 255), center=(W // 2, 440))
            text(f"Levels cleared: {TOTAL_LEVELS}", f_med, CYAN, center=(W // 2, 485))
            text(f"Coins earned: {save['coins']}", f_med, GOLD, center=(W // 2, 520))
            if int(now * 2) % 2 == 0:
                text("Press ENTER", f_med, (255, 255, 255), center=(W // 2, 600))

    present()

    # menu hints / banner cleanup
    if level_banner_timer > 0:
        level_banner_timer -= dt
    if menu_hint_timer > 0:
        menu_hint_timer -= dt
