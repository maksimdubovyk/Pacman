# ghost_ai.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, Dict, List
import random
import pygame


Vec = Tuple[int, int]
Point = Tuple[int, int]


@dataclass(frozen=True)
class Weights:
    w_dist: float = 1.0
    w_reverse: float = 3.0
    w_separation: float = 0.4
    w_jitter: float = 0.1


class GhostAI:
    """
    Евристичний AI для привидів у стилі:
    - Blinky: direct chase
    - Pinky: ambush (k tiles ahead)
    - Inky: chaotic intercept (target depends on Blinky + ahead point)
    - Clyde: herder (chase far, scatter near)
    """

    def __init__(
        self,
        step: int = 15,         # крок привида за 1 тик (у твоєму коді привиди ходять 15 px)
        tile: int = 30,         # “тайл”/клітинка логіки (Pacman ходить 30 px)
        board_size: int = 606,  # розмір поля
        seed: int = 1
    ) -> None:
        self.step = step
        self.tile = tile
        self.board_size = board_size
        self.rng = random.Random(seed)

        # Кути для scatter (можеш поміняти)
        self.scatter_targets: Dict[str, Point] = {
            "blinky": (board_size - 30, 30),                 # top-right
            "pinky": (30, 30),                               # top-left
            "inky": (board_size - 30, board_size - 30),      # bottom-right
            "clyde": (30, board_size - 30),                  # bottom-left
        }

        self.weights: Dict[str, Weights] = {
            "blinky": Weights(w_dist=1.0, w_reverse=2.5, w_separation=0.2, w_jitter=0.0),
            "pinky":  Weights(w_dist=1.0, w_reverse=2.0, w_separation=0.2, w_jitter=0.0),
            "inky":   Weights(w_dist=1.0, w_reverse=2.0, w_separation=0.7, w_jitter=0.35),
            "clyde":  Weights(w_dist=1.0, w_reverse=2.0, w_separation=0.3, w_jitter=0.05),
        }

    def set_ghost_direction(
        self,
        ghost_name: str,
        ghost: pygame.sprite.Sprite,
        pacman: pygame.sprite.Sprite,
        walls: pygame.sprite.Group,
        gate: Optional[pygame.sprite.Group] = None,
        other_ghosts: Optional[Iterable[pygame.sprite.Sprite]] = None,
        blinky: Optional[pygame.sprite.Sprite] = None,
    ) -> None:
        name = ghost_name.lower()
        other_list = [g for g in (other_ghosts or []) if g is not ghost]

        possible = self._possible_moves(ghost, walls, gate)
        if not possible:
            ghost.change_x = 0
            ghost.change_y = 0
            return

        target = self._compute_target(name, ghost, pacman, blinky)
        w = self.weights.get(name, Weights())

        best_move = self._choose_best_move(
            ghost=ghost,
            moves=possible,
            target=target,
            weights=w,
            other_ghosts=other_list,
        )

        ghost.change_x, ghost.change_y = best_move

    def _compute_target(
        self,
        name: str,
        ghost: pygame.sprite.Sprite,
        pacman: pygame.sprite.Sprite,
        blinky: Optional[pygame.sprite.Sprite],
    ) -> Point:
        pac = pacman.rect.center
        pac_dir = self._normalize_dir(getattr(pacman, "change_x", 0), getattr(pacman, "change_y", 0))

        if name == "blinky":
            return pac

        if name == "pinky":
            k = 4
            return (pac[0] + pac_dir[0] * self.tile * k, pac[1] + pac_dir[1] * self.tile * k)

        if name == "inky":
            k = 2
            ahead = (pac[0] + pac_dir[0] * self.tile * k, pac[1] + pac_dir[1] * self.tile * k)
            if blinky is None:
                return ahead
            bpos = blinky.rect.center
            return (2 * ahead[0] - bpos[0], 2 * ahead[1] - bpos[1])

        if name == "clyde":
            dist_tiles = self._manhattan(ghost.rect.center, pac) / float(self.tile)
            if dist_tiles > 6.0:
                return pac
            return self.scatter_targets["clyde"]

        return pac

    def _choose_best_move(
        self,
        ghost: pygame.sprite.Sprite,
        moves: List[Vec],
        target: Point,
        weights: Weights,
        other_ghosts: List[pygame.sprite.Sprite],
    ) -> Vec:
        cur_dir = (getattr(ghost, "change_x", 0), getattr(ghost, "change_y", 0))
        cur_dir = self._normalize_dir(cur_dir[0], cur_dir[1])

        reverse = (-cur_dir[0] * self.step, -cur_dir[1] * self.step) if cur_dir != (0, 0) else None

        best = None
        best_score = float("inf")

        for dx, dy in moves:
            next_pos = (ghost.rect.centerx + dx, ghost.rect.centery + dy)

            d = self._manhattan(next_pos, target)

            rev_pen = 0.0
            if reverse is not None and (dx, dy) == reverse and len(moves) > 1:
                rev_pen = 1000.0

            sep_pen = 0.0
            if other_ghosts:
                for g in other_ghosts:
                    dd = self._manhattan(next_pos, g.rect.center)
                    sep_pen += 1.0 / (dd + 1.0)

            jitter = self.rng.random()

            score = (
                weights.w_dist * d
                + weights.w_reverse * rev_pen
                + weights.w_separation * sep_pen * 1000.0
                + weights.w_jitter * jitter * 50.0
            )

            if score < best_score:
                best_score = score
                best = (dx, dy)

        return best if best is not None else moves[0]

    def _possible_moves(
        self,
        ghost: pygame.sprite.Sprite,
        walls: pygame.sprite.Group,
        gate: Optional[pygame.sprite.Group],
    ) -> List[Vec]:
        candidates: List[Vec] = [
            (-self.step, 0),
            ( self.step, 0),
            (0, -self.step),
            (0,  self.step),
        ]

        ok: List[Vec] = []
        for dx, dy in candidates:
            if self._can_move(ghost, dx, dy, walls, gate):
                ok.append((dx, dy))

        return ok

    def _can_move(
        self,
        sprite: pygame.sprite.Sprite,
        dx: int,
        dy: int,
        walls: pygame.sprite.Group,
        gate: Optional[pygame.sprite.Group],
    ) -> bool:
        rect = sprite.rect
        old = rect.topleft
        rect.left += dx
        rect.top += dy

        hit_wall = pygame.sprite.spritecollide(sprite, walls, False)
        hit_gate = False
        if gate is not None and gate is not False:
            hit_gate = bool(pygame.sprite.spritecollide(sprite, gate, False))

        rect.topleft = old
        return (not hit_wall) and (not hit_gate)

    @staticmethod
    def _manhattan(a: Point, b: Point) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _normalize_dir(dx: int, dy: int) -> Vec:
        # Повертає (-1,0,1) по осях
        ndx = 0 if dx == 0 else (1 if dx > 0 else -1)
        ndy = 0 if dy == 0 else (1 if dy > 0 else -1)
        return (ndx, ndy)