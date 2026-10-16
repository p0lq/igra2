"""Столкновения, линия видимости и поиск пути (A*) по сетке клеток."""
import heapq
import math


def _circle_hits_tile(x, y, r, tx, ty):
    """Пересекается ли круг (x, y, r) с квадратом клетки [tx, tx+1] x [ty, ty+1]."""
    nx = min(max(x, tx), tx + 1)
    ny = min(max(y, ty), ty + 1)
    return (x - nx) ** 2 + (y - ny) ** 2 < r * r


def blocked(x, y, r, solid):
    for ty in range(math.floor(y - r), math.floor(y + r) + 1):
        for tx in range(math.floor(x - r), math.floor(x + r) + 1):
            if solid(tx, ty) and _circle_hits_tile(x, y, r, tx, ty):
                return True
    return False


def move(ent, dx, dy, r, solid):
    """Сдвинуть сущность. Двигаем по X и по Y отдельно — так она скользит вдоль стен."""
    if dx and not blocked(ent.x + dx, ent.y, r, solid):
        ent.x += dx
    if dy and not blocked(ent.x, ent.y + dy, r, solid):
        ent.y += dy


def line_of_sight(zone, x0, y0, x1, y1):
    """Видно ли точку (x1, y1) из (x0, y0): идём по отрезку мелкими шагами и проверяем клетки."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = int(dist * 4) + 1
    start = (int(x0), int(y0))
    end = (int(x1), int(y1))
    for i in range(1, steps):
        t = i / steps
        tx = int(x0 + (x1 - x0) * t)
        ty = int(y0 + (y1 - y0) * t)
        if (tx, ty) in (start, end):
            continue
        if zone.blocks_sight(tx, ty):
            return False
    return True


NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def astar(start, goal, cost, max_nodes=1500):
    """Поиск кратчайшего пути A*.

    cost(x, y) — цена входа в клетку или None, если пройти нельзя.
    Возвращает список клеток от следующей после start до goal (или [] — пути нет).
    Эвристика — «октильное» расстояние (учитывает диагонали).
    """
    if start == goal:
        return []

    def h(p):
        dx, dy = abs(p[0] - goal[0]), abs(p[1] - goal[1])
        return max(dx, dy) + 0.41 * min(dx, dy)

    open_heap = [(h(start), 0.0, start)]
    came = {start: None}
    g = {start: 0.0}
    expanded = 0
    while open_heap:
        _, gc, cur = heapq.heappop(open_heap)
        if cur == goal:
            break
        if gc > g.get(cur, 1e9):
            continue
        expanded += 1
        if expanded > max_nodes:
            return []
        for dx, dy in NEIGHBORS:
            nx, ny = cur[0] + dx, cur[1] + dy
            c = cost(nx, ny)
            if c is None:
                continue
            if dx and dy:
                # не срезаем углы стен по диагонали
                if cost(cur[0] + dx, cur[1]) is None or cost(cur[0], cur[1] + dy) is None:
                    continue
                c *= 1.41
            ng = gc + c
            if ng < g.get((nx, ny), 1e9):
                g[(nx, ny)] = ng
                came[(nx, ny)] = cur
                heapq.heappush(open_heap, (ng + h((nx, ny)), ng, (nx, ny)))
    if goal not in came:
        return []
    path = []
    p = goal
    while p != start:
        path.append(p)
        p = came[p]
    path.reverse()
    return path
