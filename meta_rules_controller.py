from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, List
import pygame

@dataclass
class RoleSwapConfig:
    """Configuration for the 'Pacman avoids everyone -> swap roles' meta-rule."""

    safe_distance_tiles: float = 6.0
    escape_ticks_threshold: int = 60
    swap_cooldown_ticks: int = 30
    rotation_step: int = 1

@dataclass
class ConvergeConfig:
    """Configuration for the 'Pacman surrounded -> converge to Pacman' meta-rule (Criterion A: sectors)."""

    radius_tiles: float = 6.0
    required_sectors: int = 3
    hold_ticks: int = 30
    cooldown_ticks: int = 30
class MetaRulesController:
    """
    Meta-controller: if Pacman stays far from all ghosts for long enough,
    swap ghost roles (Variant A: cyclic rotation).
    """

    def __init__(
        self,
        tile: int,
        config: Optional[RoleSwapConfig] = None,
        converge_config: Optional[ConvergeConfig] = None,
    ) -> None:
        self.tile = tile
        self.cfg = config or RoleSwapConfig()
        self.converge_cfg = converge_config or ConvergeConfig()

        self.ghost_ids: List[str] = ["blinky", "pinky", "inky", "clyde"]
        self.role_map: Dict[str, str] = {gid: gid for gid in self.ghost_ids}

        # state for meta-rules
        self._escape_ticks: int = 0
        self._role_swap_cooldown: int = 0

        self._converge_ticks: int = 0
        self._converge_cooldown: int = 0


    def update(self, pacman: pygame.sprite.Sprite, ghosts: Dict[str, pygame.sprite.Sprite]) -> Dict[str, str]:
        pac = pacman.rect.center

        # Rule 2 first: converge може повністю override-нути ролі
        converge_map = self._update_converge_rule(pac, ghosts)
        if converge_map is not None:
            return converge_map

        # Rule 1: escape -> role swap
        self._update_role_swap_rule(pac, ghosts)

        return dict(self.role_map)

    def _update_converge_rule(
        self,
        pac: tuple[int, int],
        ghosts: Dict[str, pygame.sprite.Sprite],
    ) -> Optional[Dict[str, str]]:
        # cooldown зменшуємо завжди
        if self._converge_cooldown > 0:
            self._converge_cooldown -= 1

        if self._converge_ticks > 0:
            print('Converge is active')
            self._converge_ticks -= 1
            if self._converge_ticks == 0:
                self._converge_cooldown = self.converge_cfg.cooldown_ticks

            # поки converge активний — не накопичуємо escape
            self._escape_ticks = 0
            return {gid: "converge" for gid in self.ghost_ids}

        # detect surround тільки якщо нема cooldown
        if self._converge_cooldown != 0:
            return None

        sectors = set()
        radius_px = self.converge_cfg.radius_tiles * float(self.tile)

        for gid in self.ghost_ids:
            g = ghosts.get(gid)
            if g is None:
                continue

            gx, gy = g.rect.center
            dx = gx - pac[0]
            dy = gy - pac[1]

            # беремо тільки привидів у радіусі (Manhattan)
            if abs(dx) + abs(dy) > radius_px:
                continue

            # квадранти: NE, NW, SW, SE
            if dx >= 0 and dy < 0:
                sectors.add("NE")
            elif dx < 0 and dy < 0:
                sectors.add("NW")
            elif dx < 0 and dy >= 0:
                sectors.add("SW")
            else:
                sectors.add("SE")

        if len(sectors) >= self.converge_cfg.required_sectors:
            self._converge_ticks = self.converge_cfg.hold_ticks
            self._escape_ticks = 0
            return {gid: "converge" for gid in self.ghost_ids}

        return None

    def _update_role_swap_rule(
        self,
        pac: tuple[int, int],
        ghosts: Dict[str, pygame.sprite.Sprite],
    ) -> None:
        min_dist = self._min_dist_to_pacman_tiles(pac, ghosts)

        if min_dist >= self.cfg.safe_distance_tiles:
            self._escape_ticks += 1
        else:
            self._escape_ticks = 0

        if self._role_swap_cooldown > 0:
            self._role_swap_cooldown -= 1

        if self._escape_ticks >= self.cfg.escape_ticks_threshold and self._role_swap_cooldown == 0:
            print('Roles have been swapped')
            self._swap_roles()
            self._escape_ticks = 0
            self._role_swap_cooldown = self.cfg.swap_cooldown_ticks

    def _min_dist_to_pacman_tiles(
        self,
        pac: tuple[int, int],
        ghosts: Dict[str, pygame.sprite.Sprite],
    ) -> float:
        min_dist = float("inf")
        for gid in self.ghost_ids:
            g = ghosts.get(gid)
            if g is None:
                continue
            d = (abs(g.rect.centerx - pac[0]) + abs(g.rect.centery - pac[1])) / float(self.tile)
            min_dist = min(min_dist, d)
        return min_dist


    def _swap_roles(self) -> None:
        step = self.cfg.rotation_step % len(self.ghost_ids)
        if step == 0:
            return

        current_roles = [self.role_map[gid] for gid in self.ghost_ids]
        rotated = current_roles[-step:] + current_roles[:-step]
        self.role_map = {gid: role for gid, role in zip(self.ghost_ids, rotated)}

    def role_to_ghost(self, ghosts: Dict[str, pygame.sprite.Sprite]) -> Dict[str, pygame.sprite.Sprite]:
        inv: Dict[str, pygame.sprite.Sprite] = {}
        for gid, role in self.role_map.items():
            if gid in ghosts:
                inv[role] = ghosts[gid]
        return inv
