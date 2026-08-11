"""«Поймай импрессиониста» — музейная аркада на pygame.

На героя летит бесконечный поток картин. Импрессионистов (im_*) нужно
ловить — за каждую пойманную картину растёт счёт. От картин других жанров
(noim_*) нужно уворачиваться: попадание отнимает одну жизнь.

Управление: стрелки вверх/вниз (или W/S), P — пауза, Esc — выход.
"""

import math
import random
import sys
from pathlib import Path

import pygame

ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "images" / "game"

WIDTH, HEIGHT = 900, 600
FPS = 60

PLAYER_X = 100
PLAYER_SPEED = 430
PLAYER_SIZE = 56

PAINTING_SIZE = 112
FRAME_IM = (214, 170, 64)     # золотая рама у импрессионистов
FRAME_NOIM = (110, 116, 128)  # серая рама у остальных жанров

START_LIVES = 3
START_SPEED = 150.0
MAX_SPEED = 340.0
SPEED_RAMP = 4.2              # прирост скорости, px/s за секунду
START_SPAWN_INTERVAL = 1.15
MIN_SPAWN_INTERVAL = 0.40
SPAWN_RAMP = 0.045            # насколько секунд убывает интервал за секунду
IM_PROBABILITY = 0.55
INVULNERABLE_TIME = 2.0

LIGHT = (238, 238, 230)
GOLD = (245, 220, 140)
GREY = (190, 198, 210)


def load_font(size, bold=False):
    """Шрифт с кириллицей; фолбэк на встроенный freesansbold."""
    for name in ("segoeui", "arial", "calibri", "dejavusans", "notosans"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def make_background():
    """Градиентное «музейное» фоновое полотно."""
    bg = pygame.Surface((WIDTH, HEIGHT))
    top = (16, 28, 46)
    bottom = (52, 74, 100)
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        row = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        pygame.draw.line(bg, row, (0, y), (WIDTH, y))
    # плинтус галереи
    pygame.draw.rect(bg, (28, 36, 46), (0, HEIGHT - 90, WIDTH, 90))
    pygame.draw.line(bg, (70, 82, 96), (0, HEIGHT - 90), (WIDTH, HEIGHT - 90), 2)
    return bg


def frame_painting(image, accent):
    """Белая паспарту-подложка и цветная рама вокруг картины."""
    margin = 9
    size = image.get_width() + margin * 2
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    out.fill((250, 248, 240))
    pygame.draw.rect(out, accent, out.get_rect(), width=4)
    out.blit(image, (margin, margin))
    return out


def draw_heart(surface, cx, cy, size, color):
    r = size // 4
    left = cx - size // 2
    top = cy - size // 2
    pygame.draw.circle(surface, color, (left + r, top + r), r)
    pygame.draw.circle(surface, color, (left + size - r, top + r), r)
    pygame.draw.polygon(surface, color, [
        (left, top + size * 0.38),
        (cx, top + size * 0.95),
        (left + size, top + size * 0.38),
    ])


class Painting:

    def __init__(self, image, impressionist, speed, y):
        self.image = image
        self.impressionist = impressionist
        self.speed = speed
        self.rect = self.image.get_rect(midleft=(WIDTH + 20, y))
        self.base_y = y
        self.phase = random.uniform(0.0, math.tau)
        self.osc_amp = random.uniform(26.0, 60.0)
        self.osc_freq = random.uniform(1.1, 2.0)
        self.time = 0.0

    def update(self, dt):
        self.time += dt
        self.rect.x -= self.speed * dt
        center_y = self.base_y + math.sin(self.time * self.osc_freq + self.phase) * self.osc_amp
        self.rect.centery = max(20, min(HEIGHT - 20, center_y))

    def draw(self, surface, offset):
        surface.blit(self.image, self.rect.move(offset))


class Player:

    def __init__(self):
        self.rect = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
        self.rect.midleft = (PLAYER_X, HEIGHT // 2)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.rect.y -= PLAYER_SPEED * dt
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.rect.y += PLAYER_SPEED * dt
        self.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))

    def hitbox(self):
        return self.rect.inflate(-12, -12)

    def draw(self, surface, offset, visible):
        if not visible:
            return
        rect = self.rect.move(offset)
        cx = rect.centerx
        bottom = rect.bottom
        # тело посетителя музея
        body = pygame.Rect(0, 0, 26, 32)
        body.midbottom = (cx, bottom)
        pygame.draw.rect(surface, (47, 98, 163), body, border_radius=9)
        # голова
        pygame.draw.circle(surface, (232, 198, 168), (cx, bottom - 40), 12)
        # берет
        pygame.draw.ellipse(surface, (194, 62, 74), (cx - 15, bottom - 54, 30, 10))
        # палитра в руке
        pygame.draw.ellipse(surface, (122, 82, 46), (cx + 10, bottom - 24, 20, 14))
        pygame.draw.circle(surface, (232, 198, 168), (cx + 9, bottom - 30), 5)


class Game:

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Поймай импрессиониста")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = {
            "small": load_font(20),
            "medium": load_font(28, bold=True),
            "large": load_font(44, bold=True),
            "huge": load_font(66, bold=True),
        }
        self.bg = make_background()
        self.im_frames = self._load_frames(True, FRAME_IM)
        self.noim_frames = self._load_frames(False, FRAME_NOIM)
        self.reset()
        self.state = "menu"

    def _load_frames(self, impressionist, accent):
        prefix = "im_" if impressionist else "noim_"
        frames = []
        for path in sorted(ASSETS_DIR.glob(prefix + "*.jpg")):
            image = pygame.image.load(str(path)).convert_alpha()
            image = pygame.transform.smoothscale(
                image, (PAINTING_SIZE, PAINTING_SIZE))
            frames.append(frame_painting(image, accent))
        return frames

    def reset(self):
        self.player = Player()
        self.paintings = []
        self.score = 0
        self.lives = START_LIVES
        self.elapsed = 0.0
        self.spawn_timer = 0.5
        self.invulnerable = 0.0
        self.feedback = None
        self.feedback_timer = 0.0
        self.shake = 0.0
        self.paused = False

    def spawn_painting(self, speed):
        impressionist = random.random() < IM_PROBABILITY
        pool = self.im_frames if impressionist else self.noim_frames
        image = pygame.transform.rotate(
            random.choice(pool), random.uniform(-8.0, 8.0))
        y = random.uniform(80, HEIGHT - 80)
        return Painting(image, impressionist, speed, y)

    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            raise SystemExit
        if self.state == "menu":
            self.state = "playing"
            return
        if self.state == "over":
            if key == pygame.K_r:
                self.reset()
                self.state = "playing"
            return
        if key == pygame.K_p:
            self.paused = not self.paused

    def update(self, dt):
        if self.state != "playing" or self.paused:
            return
        self.elapsed += dt
        self.player.update(dt)

        speed = min(MAX_SPEED, START_SPEED + self.elapsed * SPEED_RAMP)
        spawn_interval = max(MIN_SPAWN_INTERVAL,
                             START_SPAWN_INTERVAL - self.elapsed * SPAWN_RAMP)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.paintings.append(self.spawn_painting(speed))
            self.spawn_timer = spawn_interval * random.uniform(0.7, 1.3)

        hitbox = self.player.hitbox()
        for painting in list(self.paintings):
            painting.update(dt)
            if painting.rect.right < -20:
                self.paintings.remove(painting)
                continue
            if painting.rect.inflate(-14, -14).colliderect(hitbox):
                self.paintings.remove(painting)
                if painting.impressionist:
                    self.score += 1
                    self.feedback = ("Поймал! +1", (120, 230, 140))
                    self.feedback_timer = 0.9
                elif self.invulnerable <= 0.0:
                    self.lives -= 1
                    self.invulnerable = INVULNERABLE_TIME
                    self.shake = 0.35
                    self.feedback = ("Попался! -1 жизнь", (240, 110, 110))
                    self.feedback_timer = 1.0
                    if self.lives <= 0:
                        self.state = "over"

        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.feedback_timer = max(0.0, self.feedback_timer - dt)
        self.shake = max(0.0, self.shake - dt)

    def draw(self):
        offset = (0, 0)
        if self.shake > 0:
            offset = (random.randint(-5, 5), random.randint(-5, 5))
        self.screen.blit(self.bg, offset)
        for painting in self.paintings:
            painting.draw(self.screen, offset)
        visible = self.invulnerable <= 0 or (pygame.time.get_ticks() // 100) % 2 == 0
        self.player.draw(self.screen, offset, visible)
        self.draw_hud()

        if self.feedback_timer > 0 and self.state == "playing":
            text = self.font["medium"].render(self.feedback[0], True, self.feedback[1])
            self.screen.blit(text, text.get_rect(
                midbottom=(self.player.rect.centerx, self.player.rect.top - 26)))

        if self.state == "menu":
            self.draw_menu()
        elif self.state == "over":
            self.draw_game_over()

        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((8, 12, 20, 160))
            self.screen.blit(overlay, (0, 0))
            text = self.font["large"].render("ПАУЗА", True, LIGHT)
            hint = self.font["small"].render("P — продолжить, Esc — выход", True, GREY)
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30)))
            self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))

        pygame.display.flip()

    def draw_hud(self):
        bar = pygame.Surface((WIDTH, 52), pygame.SRCALPHA)
        bar.fill((12, 18, 28, 170))
        self.screen.blit(bar, (0, 0))

        score_text = self.font["medium"].render(f"Счёт: {self.score}", True, GOLD)
        self.screen.blit(score_text, (16, 12))

        minutes, seconds = divmod(int(self.elapsed), 60)
        time_text = self.font["small"].render(
            f"Время: {minutes:02d}:{seconds:02d}", True, (200, 208, 220))
        self.screen.blit(time_text, time_text.get_rect(midtop=(WIDTH // 2, 16)))

        for i in range(START_LIVES):
            cx = WIDTH - 30 - i * 34
            color = (232, 96, 96) if i < self.lives else (60, 70, 84)
            draw_heart(self.screen, cx, 24, 26, color)

    def draw_menu(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 10, 16, 170))
        self.screen.blit(overlay, (0, 0))

        title1 = self.font["huge"].render("ПОЙМАЙ", True, (242, 208, 110))
        title2 = self.font["huge"].render("ИМПРЕССИОНИСТА", True, LIGHT)
        self.screen.blit(title1, title1.get_rect(midtop=(WIDTH // 2, 110)))
        self.screen.blit(title2, title2.get_rect(midtop=(WIDTH // 2, 190)))

        line1 = self.font["medium"].render(
            "На героя летит бесконечный поток картин.", True, (220, 226, 236))
        line2 = self.font["small"].render(
            "Ловите импрессионистов и уворачивайтесь от картин других жанров.",
            True, GREY)
        self.screen.blit(line1, line1.get_rect(midtop=(WIDTH // 2, 330)))
        self.screen.blit(line2, line2.get_rect(midtop=(WIDTH // 2, 375)))

        controls = self.font["small"].render(
            "↑ / ↓ — движение    P — пауза    Esc — выход", True, (170, 180, 195))
        start = self.font["medium"].render(
            "Нажмите любую клавишу", True, (140, 225, 160))
        self.screen.blit(controls, controls.get_rect(midtop=(WIDTH // 2, 430)))
        self.screen.blit(start, start.get_rect(midtop=(WIDTH // 2, 480)))

    def draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 8, 14, 190))
        self.screen.blit(overlay, (0, 0))

        title = self.font["large"].render("ИГРА ОКОНЧЕНА", True, LIGHT)
        score = self.font["large"].render(f"Счёт: {self.score}", True, GOLD)
        hint = self.font["small"].render(
            "R — сыграть ещё раз    Esc — выход", True, GREY)
        self.screen.blit(title, title.get_rect(midtop=(WIDTH // 2, 200)))
        self.screen.blit(score, score.get_rect(midtop=(WIDTH // 2, 300)))
        self.screen.blit(hint, hint.get_rect(midtop=(WIDTH // 2, 400)))

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    self.on_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN and self.state == "menu":
                    self.state = "playing"
            self.update(dt)
            self.draw()


def main():
    pygame.init()
    game = Game()
    game.run()
    pygame.quit()


if __name__ == "__main__":
    main()