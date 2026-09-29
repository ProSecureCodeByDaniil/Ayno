(function () {
  var c = document.getElementById('starfield');
  if (!c) return;
  var x = c.getContext('2d');
  var w, h, s = [];

  function resize() {
    w = c.width = innerWidth;
    h = c.height = innerHeight;
    s = [];
    for (var i = 0; i < 200; i++) {
      s.push({
        x: Math.random() * w,
        y: Math.random() * h,
        z: Math.random() * 0.8 + 0.2,
        r: Math.random() * 1.5 + 0.5
      });
    }
  }

  function draw() {
    x.clearRect(0, 0, w, h);
    for (var i = 0; i < s.length; i++) {
      var p = s[i];
      x.globalAlpha = p.z * 0.8 + 0.2;
      x.fillStyle = p.z > 0.6 ? '#a8d8ff' : '#fff';
      x.beginPath();
      x.arc(p.x, p.y, p.r, 0, 6.28);
      x.fill();
      p.y += p.z * 0.5;
      if (p.y > h) { p.y = 0; p.x = Math.random() * w; }
    }
    requestAnimationFrame(draw);
  }

  resize();
  draw();
  addEventListener('resize', resize);
})();