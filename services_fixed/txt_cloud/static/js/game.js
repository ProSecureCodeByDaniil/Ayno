(function () {
  "use strict";

  var FILES_URL = (window.GAME_CONFIG && window.GAME_CONFIG.filesUrl) || "/files";

  var canvas = document.getElementById("gameCanvas");
  var ctx = canvas.getContext("2d");
  var W, H;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener("resize", resize);

  var menu = document.getElementById("gameMenu");
  var hud = document.getElementById("gameHud");
  var heartsEl = document.getElementById("hearts");
  var scoreEl = document.getElementById("scoreVal");
  var nameInput = document.getElementById("playerName");
  var startBtn = document.getElementById("startBtn");
  var closeBtn = document.getElementById("closeBtn");
  var lbEl = document.getElementById("leaderboard");
  var hintEl = document.getElementById("menuHint");
  var titleEl = document.getElementById("gameTitle");
  var subtitleEl = document.getElementById("gameSubtitle");
  var gameOverGif = document.getElementById("gameOverGif");

  var LS_KEY = "txcloud_hyperspace_defender_top_v1";
  var MAX_SCORES = 10;

  function loadScores() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (!raw) return [];
      var arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }

  function saveScore(name, score) {
    var arr = loadScores();
    arr.push({ name: String(name).slice(0, 16), score: score | 0, ts: Date.now() });
    arr.sort(function (a, b) { return b.score - a.score; });
    var top = arr.slice(0, MAX_SCORES);
    try { localStorage.setItem(LS_KEY, JSON.stringify(top)); } catch (e) {}
    return top;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderLeaderboard() {
    var arr = loadScores();
    if (!arr.length) {
      lbEl.innerHTML = '<li style="color:#8b93a1;text-align:center;">Пока никто не играл</li>';
      return;
    }
    lbEl.innerHTML = arr.map(function (e, i) {
      return '<li style="display:flex;justify-content:space-between;padding:5px 10px;border-bottom:1px dashed rgba(255,232,31,.15);">' +
        '<span style="color:#4fc3f7;width:24px;">' + (i + 1) + '.</span>' +
        '<span style="flex:1;color:#e6e8eb;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(e.name) + '</span>' +
        '<span style="color:#ffe81f;font-weight:700;">' + e.score + '</span></li>';
    }).join("");
  }

  var S = null;
  var raf = null;
  var lastT = 0;

  function makeStars(n) {
    var a = [];
    for (var i = 0; i < n; i++) {
      a.push({ x: Math.random() * W, y: Math.random() * H, z: Math.random() * 0.9 + 0.1 });
    }
    return a;
  }

  function newState(name) {
    return {
      name: name,
      stars: makeStars(180),
      player: { x: W / 2, y: H - 60, speed: 340, fireCd: 0, invuln: 1.2 },
      bullets: [], enemyBullets: [], enemies: [], asteroids: [],
      score: 0, lives: 3, t: 0,
      spawnEnemy: 1.4, spawnAsteroid: 1.0,
      over: false, shake: 0
    };
  }

  var keys = Object.create(null);
  window.addEventListener("keydown", function (e) {
    var k = e.key.toLowerCase();
    if (["arrowleft", "arrowright", "arrowup", "arrowdown", " ", "a", "d"].indexOf(k) >= 0) e.preventDefault();
    keys[k] = true;
    if (k === " " && S && !S.over) shootBullet();
  }, { passive: false });
  window.addEventListener("keyup", function (e) { keys[e.key.toLowerCase()] = false; });

  function spawnAsteroid() {
    var r = 16 + Math.random() * 24;
    var pts = [], n = 8 + Math.floor(Math.random() * 4);
    for (var i = 0; i < n; i++) {
      var a = (i / n) * Math.PI * 2, rr = r * (0.75 + Math.random() * 0.45);
      pts.push({ a: a, r: rr });
    }
    S.asteroids.push({
      x: 20 + Math.random() * (W - 40), y: -r - 10,
      r: r, vx: (Math.random() - 0.5) * 30, vy: 60 + Math.random() * 70,
      angle: 0, spin: (Math.random() - 0.5) * 2, points: pts
    });
  }

  function spawnEnemy() {
    S.enemies.push({
      x: 50 + Math.random() * (W - 100), y: -40, w: 36, h: 30,
      vx: (Math.random() - 0.5) * 60, vy: 40 + Math.random() * 40,
      shootCd: 0.8 + Math.random() * 1.2
    });
  }

  function shootBullet() {
    if (!S || S.over || S.player.fireCd > 0) return;
    S.player.fireCd = 0.18;
    S.bullets.push({ x: S.player.x - 3, y: S.player.y - 16, vy: -520 });
    S.bullets.push({ x: S.player.x + 3, y: S.player.y - 16, vy: -520 });
  }

  function damagePlayer() {
    if (!S || S.over || S.player.invuln > 0) return;
    S.lives -= 1; S.player.invuln = 1.6; S.shake = 1;
    updateHearts();
    if (S.lives <= 0) gameOver();
  }

  function updateHearts() {
    var html = "";
    for (var i = 0; i < 3; i++) {
      html += i < S.lives ? "❤" : '<span style="opacity:.25;">❤</span>';
    }
    heartsEl.innerHTML = html;
  }

  function hitCircle(x1, y1, r1, x2, y2, r2) {
    var dx = x1 - x2, dy = y1 - y2, rr = r1 + r2;
    return dx * dx + dy * dy < rr * rr;
  }
  function hitRect(ax, ay, aw, ah, bx, by, bw, bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }

  function update(dt) {
    if (!S) return;
    S.t += dt;
    if (S.shake > 0) S.shake = Math.max(0, S.shake - dt * 3);
    if (S.over) return;

    for (var i = 0; i < S.stars.length; i++) {
      var st = S.stars[i];
      st.y += (40 + st.z * 260) * dt * (1 + S.t * 0.02);
      if (st.y > H) { st.y = -2; st.x = Math.random() * W; }
    }

    var p = S.player;
    if (p.invuln > 0) p.invuln -= dt;
    if (p.fireCd > 0) p.fireCd -= dt;
    var dx = 0;
    if (keys["a"] || keys["arrowleft"]) dx -= 1;
    if (keys["d"] || keys["arrowright"]) dx += 1;
    p.x += dx * p.speed * dt;
    if (p.x < 20) p.x = 20;
    if (p.x > W - 20) p.x = W - 20;

    for (var i = S.bullets.length - 1; i >= 0; i--) {
      var b = S.bullets[i]; b.y += b.vy * dt;
      if (b.y < -10) S.bullets.splice(i, 1);
    }
    for (var i = S.enemyBullets.length - 1; i >= 0; i--) {
      var b = S.enemyBullets[i]; b.y += b.vy * dt;
      if (b.y > H + 10) S.enemyBullets.splice(i, 1);
    }

    S.spawnAsteroid -= dt; S.spawnEnemy -= dt;
    if (S.spawnAsteroid <= 0) {
      spawnAsteroid();
      S.spawnAsteroid = Math.max(0.35, 1.1 - S.t * 0.008) * (0.7 + Math.random() * 0.6);
    }
    if (S.spawnEnemy <= 0) {
      spawnEnemy();
      S.spawnEnemy = Math.max(0.7, 2.0 - S.t * 0.01) * (0.8 + Math.random() * 0.6);
    }

    for (var i = S.asteroids.length - 1; i >= 0; i--) {
      var a = S.asteroids[i];
      a.x += a.vx * dt; a.y += a.vy * dt; a.angle += a.spin * dt;
      if (a.y - a.r > H + 10) { S.asteroids.splice(i, 1); continue; }
      if (hitCircle(p.x, p.y, 14, a.x, a.y, a.r)) {
        S.asteroids.splice(i, 1); damagePlayer();
      }
    }

    for (var i = S.enemies.length - 1; i >= 0; i--) {
      var e = S.enemies[i];
      e.x += e.vx * dt; e.y += e.vy * dt;
      if (e.x < 20 || e.x > W - 20) e.vx *= -1;
      e.shootCd -= dt;
      if (e.shootCd <= 0 && e.y > 0) {
        e.shootCd = 0.9 + Math.random() * 1.1;
        S.enemyBullets.push({ x: e.x, y: e.y + 14, vy: 220 + Math.random() * 80 });
      }
      if (e.y > H + 40) { S.enemies.splice(i, 1); continue; }

      var killed = false;
      for (var j = S.bullets.length - 1; j >= 0; j--) {
        var b = S.bullets[j];
        if (Math.abs(b.x - e.x) < e.w / 2 && Math.abs(b.y - e.y) < e.h / 2) {
          S.bullets.splice(j, 1); killed = true; break;
        }
      }
      if (killed) {
        S.enemies.splice(i, 1);
        S.score += 15;
        scoreEl.textContent = S.score;
        continue;
      }
      if (hitRect(p.x - 14, p.y - 14, 28, 28, e.x - e.w / 2, e.y - e.h / 2, e.w, e.h)) {
        S.enemies.splice(i, 1); damagePlayer();
      }
    }

    for (var i = S.enemyBullets.length - 1; i >= 0; i--) {
      var b = S.enemyBullets[i];
      if (Math.abs(b.x - p.x) < 12 && Math.abs(b.y - p.y) < 14) {
        S.enemyBullets.splice(i, 1); damagePlayer();
      }
    }
  }

  function draw() {
    ctx.save();
    if (S && S.shake > 0) {
      ctx.translate((Math.random() - 0.5) * 6 * S.shake, (Math.random() - 0.5) * 6 * S.shake);
    }
    ctx.fillStyle = "#000";
    ctx.fillRect(-10, -10, W + 20, H + 20);

    if (S) {
      for (var i = 0; i < S.stars.length; i++) {
        var st = S.stars[i];
        ctx.fillStyle = st.z > 0.7 ? "#a8d8ff" : "#ffffff";
        ctx.globalAlpha = 0.4 + st.z * 0.6;
        var sz = 0.6 + st.z * 1.8;
        ctx.fillRect(st.x, st.y, sz, sz);
      }
      ctx.globalAlpha = 1;

      for (var i = 0; i < S.asteroids.length; i++) {
        var a = S.asteroids[i];
        ctx.save(); ctx.translate(a.x, a.y); ctx.rotate(a.angle);
        ctx.beginPath();
        var pts = a.points;
        for (var j = 0; j < pts.length; j++) {
          var pt = pts[j], x = Math.cos(pt.a) * pt.r, y = Math.sin(pt.a) * pt.r;
          if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.fillStyle = "#3a2f24"; ctx.fill();
        ctx.strokeStyle = "#8a6f4a"; ctx.lineWidth = 1.5; ctx.stroke();
        ctx.restore();
      }

      for (var i = 0; i < S.enemies.length; i++) drawTie(S.enemies[i].x, S.enemies[i].y);

      for (var i = 0; i < S.enemyBullets.length; i++) {
        var b = S.enemyBullets[i];
        ctx.fillStyle = "#ff3b3b"; ctx.shadowColor = "#ff3b3b"; ctx.shadowBlur = 12;
        ctx.beginPath(); ctx.arc(b.x, b.y, 3.5, 0, Math.PI * 2); ctx.fill();
      }
      for (var i = 0; i < S.bullets.length; i++) {
        var b = S.bullets[i];
        ctx.fillStyle = "#4fc3f7"; ctx.shadowColor = "#4fc3f7"; ctx.shadowBlur = 14;
        ctx.fillRect(b.x - 1.5, b.y - 6, 3, 12);
      }
      ctx.shadowBlur = 0;

      var p = S.player;
      var blink = p.invuln > 0 && Math.floor(S.t * 12) % 2 === 0;
      if (!blink) drawXWing(p.x, p.y);
    }
    ctx.restore();
  }

  function drawXWing(cx, cy) {
    ctx.save(); ctx.translate(cx, cy);
    ctx.fillStyle = "#dfe6ef";
    ctx.beginPath();
    ctx.moveTo(0, -18); ctx.lineTo(5, -6); ctx.lineTo(4, 12);
    ctx.lineTo(-4, 12); ctx.lineTo(-5, -6); ctx.closePath(); ctx.fill();
    ctx.fillStyle = "#4fc3f7";
    ctx.beginPath(); ctx.arc(0, -8, 2.5, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#dfe6ef"; ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-3, -4); ctx.lineTo(-16, 6);
    ctx.moveTo(-3, 4);  ctx.lineTo(-16, -2);
    ctx.moveTo(3, -4);  ctx.lineTo(16, 6);
    ctx.moveTo(3, 4);   ctx.lineTo(16, -2);
    ctx.stroke();
    ctx.fillStyle = "#ff8a3d"; ctx.shadowColor = "#ff8a3d"; ctx.shadowBlur = 12;
    ctx.fillRect(-8, 10, 3, 4); ctx.fillRect(5, 10, 3, 4);
    ctx.shadowBlur = 0; ctx.restore();
  }

  function drawTie(cx, cy) {
    ctx.save(); ctx.translate(cx, cy);
    ctx.fillStyle = "#5a6370";
    ctx.fillRect(-18, -10, 5, 20); ctx.fillRect(13, -10, 5, 20);
    ctx.beginPath(); ctx.arc(0, 0, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#2b323f"; ctx.fill();
    ctx.strokeStyle = "#8b93a1"; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = "#ff3b3b"; ctx.shadowColor = "#ff3b3b"; ctx.shadowBlur = 10;
    ctx.fill(); ctx.shadowBlur = 0; ctx.restore();
  }

  function loop(t) {
    if (!lastT) lastT = t;
    var dt = (t - lastT) / 1000; lastT = t;
    if (dt > 0.05) dt = 0.05;
    update(dt); draw();
    if (S && S.over) { raf = null; return; }
    raf = requestAnimationFrame(loop);
  }

  function showMenu() {
    menu.style.display = "flex";
    hud.style.display = "none";
    renderLeaderboard();
    nameInput.focus();
  }
  function hideMenu() {
    menu.style.display = "none";
    hud.style.display = "flex";
  }

  function startGame() {
    var name = nameInput.value.trim();
    if (!name) {
      hintEl.textContent = "Сначала введите имя пилота!";
      nameInput.focus();
      return;
    }
    hintEl.textContent = "";
    S = newState(name);
    updateHearts();
    scoreEl.textContent = "0";
    titleEl.textContent = "HYPERSPACE DEFENDER";
    subtitleEl.textContent = "«Войди в гиперпространство, пилот»";
    if (gameOverGif) gameOverGif.hidden = true;
    hideMenu();
    lastT = 0;
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(loop);
  }

  function gameOver() {
    if (!S) return;
    S.over = true;
    var top = saveScore(S.name, S.score);
    var place = -1;
    for (var i = 0; i < top.length; i++) {
      if (top[i].name === S.name && top[i].score === S.score) { place = i + 1; break; }
    }
    titleEl.textContent = "GAME OVER";
    subtitleEl.textContent = "Пилот " + S.name + ", ваш счёт: " + S.score +
      (place > 0 ? " — место №" + place : "");
    if (gameOverGif) gameOverGif.hidden = false;
    showMenu();
  }

  function closeGame() {
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    S = null;
    window.location.href = FILES_URL;
  }

  nameInput.addEventListener("input", function () {
    startBtn.disabled = nameInput.value.trim().length === 0;
    hintEl.textContent = "";
  });
  nameInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !startBtn.disabled) startGame();
  });
  startBtn.addEventListener("click", startGame);
  closeBtn.addEventListener("click", closeGame);

  // Демо-звёзды за меню, пока игрок не стартанул
  S = newState("menu-demo");
  S.over = true;
  lastT = 0;
  raf = requestAnimationFrame(loop);
  showMenu();
  renderLeaderboard();
})();