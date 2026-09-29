(function () {
  var REGISTER_URL = window.REGISTER_URL;
  var textEl      = document.getElementById('jabbaText');
  var inputDiv    = document.getElementById('jabbaInput');
  var field       = document.getElementById('jabbaField');
  var btn         = document.getElementById('jabbaBtn');
  var continueBtn = document.getElementById('jabbaContinue');

  var state = { login: '', password: '' };

  function typeWrite(el, text, cb) {
    el.textContent = '';
    var i = 0;
    var timer = setInterval(function () {
      if (i < text.length) { el.textContent += text[i]; i++; }
      else { clearInterval(timer); if (cb) cb(); }
    }, 22);
  }

  function showContinue(cb) {
    inputDiv.hidden = true;
    continueBtn.hidden = false;
    continueBtn.disabled = false;
    continueBtn.focus();

    continueBtn.onclick = function () {
      continueBtn.disabled = true;
      continueBtn.onclick = null;
      continueBtn.hidden = true;
      cb();
    };
  }

  function showInput(placeholder, cb) {
    continueBtn.hidden = true;
    continueBtn.disabled = false;
    continueBtn.onclick = null;

    inputDiv.hidden = false;
    field.value = '';
    field.placeholder = placeholder;
    field.focus();

    function submitInput() {
      var val = field.value.trim();
      if (!val) { field.focus(); return; }
      field.onkeydown = null;
      btn.onclick = null;
      inputDiv.hidden = true;
      cb(val);
    }

    btn.onclick = submitInput;
    field.onkeydown = function (e) {
      if (e.key === 'Enter') { e.preventDefault(); submitInput(); }
    };
  }

  function submit(login, password) {
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = REGISTER_URL;
    var i1 = document.createElement('input');
    i1.type = 'hidden'; i1.name = 'login'; i1.value = login;
    var i2 = document.createElement('input');
    i2.type = 'hidden'; i2.name = 'password'; i2.value = password;
    form.appendChild(i1); form.appendChild(i2);
    document.body.appendChild(form);
    form.submit();
  }

  function reactToLogin(name) {
    var n = name.toLowerCase();

    if (n.indexOf('jabba') >= 0 || n.indexOf('джабб') >= 0) {
      return '«' + name + '?! Ты назвался моим именем? Смело. Даже слишком смело для пилота.»';
    }
    if (n.indexOf('han') >= 0 || n.indexOf('хан') >= 0 || n.indexOf('solo') >= 0 || n.indexOf('соло') >= 0) {
      return '«' + name + '... Хан Соло, значит? У меня к нему должок. Что ж, посмотрим, чего стоишь ты.»';
    }
    if (n.indexOf('vader') >= 0 || n.indexOf('вейдер') >= 0 || n.indexOf('darth') >= 0 || n.indexOf('дарт') >= 0) {
      return '«' + name + '... Тёмная сторона, говоришь? Ладно, но платить будешь как все.»';
    }
    if (n.indexOf('luke') >= 0 || n.indexOf('люк') >= 0 || n.indexOf('skywalker') >= 0) {
      return '«' + name + '... Надеюсь, ты не такой шумный, как тот джедай с Татуина.»';
    }
    if (n.indexOf('yoda') >= 0 || n.indexOf('йода') >= 0) {
      return '«' + name + '? Мал ты ростом, чтобы так называться. Но ладно.»';
    }
    if (name.length <= 2) {
      return '«' + name + '? Так коротко, что даже вуки не выговорит? Хм. Записываю.»';
    }
    if (name.length >= 30) {
      return '«' + name + '?! Это имя или координаты в гиперпространстве?»';
    }

    var generic = [
      '«' + name + '... Неплохо. Не Хан Соло, но сойдёт.»',
      '«' + name + '? Запишу тебя в свои списки. Не подведи, пилот.»',
      '«' + name + '. Хм. Надеюсь, ты принёс кредиты. Шутка. Или нет.»',
      '«' + name + '... Звучит как имя того, кто мне должен. Но ладно, регистрирую.»',
      '«' + name + '. Записал. Должок за тобой, пилот.»'
    ];
    return generic[Math.floor(Math.random() * generic.length)];
  }

  var steps = [
    { say: '«Бо-о-о-о! Кто это тут у нас? Ещё один пилот, ищущий приключений в облаке? ' +
           'Назови своё имя — я занесу тебя в свои списки...»' },
    { ask: { placeholder: 'Введите логин', key: 'login' } },
    { say: function () {
        return reactToLogin(state.login) + '\n\n' +
               '«Теперь назови секретное слово, которое будешь использовать для входа. ' +
               'Пусть даже Империя не догадается.»';
    } },
    { ask: { placeholder: 'Введите пароль', key: 'password' } },
    { say: function () {
        return state.password.length < 4
          ? '«Ха! Такой пароль даже дроид-астромеханик подберёт. Но так и быть — записываю.»'
          : '«Хорошо-о-о. Добро пожаловать в мою коллекцию, пилот!»';
    } },
    { submit: true }
  ];

  var stepIndex = 0;

  function runStep() {
    if (stepIndex >= steps.length) return;
    var step = steps[stepIndex++];

    if (step.say !== undefined) {
      var text = (typeof step.say === 'function') ? step.say() : step.say;
      typeWrite(textEl, text, function () {
        showContinue(runStep);
      });
      return;
    }

    if (step.ask) {
      showInput(step.ask.placeholder, function (val) {
        state[step.ask.key] = val;
        runStep();
      });
      return;
    }

    if (step.submit) {
      submit(state.login, state.password);
    }
  }

  runStep();
})();