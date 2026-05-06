let time = 25 * 60;
let timerInterval;
let isRunning = false;
let isWork = true;

const timerDisplay = document.getElementById("timer");
const modeDisplay = document.getElementById("mode");

// popup control
document.getElementById("openTimer").onclick = () => {
  document.getElementById("pomodoroModal").style.display = "block";
};

document.getElementById("closeTimer").onclick = () => {
  document.getElementById("pomodoroModal").style.display = "none";
};

// format time
function updateDisplay() {
  let minutes = Math.floor(time / 60);
  let seconds = time % 60;
  timerDisplay.textContent =
    `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
}

// start
function startTimer() {
  if (isRunning) return;
  isRunning = true;

  timerInterval = setInterval(() => {
    if (time > 0) {
      time--;
      updateDisplay();
    } else {
      switchMode();
    }
  }, 1000);
}

// pause
function pauseTimer() {
  clearInterval(timerInterval);
  isRunning = false;
}

// reset
function resetTimer() {
  pauseTimer();
  isWork = true;
  time = 25 * 60;
  modeDisplay.textContent = "Work Time";
  updateDisplay();
}

// switch mode
function switchMode() {
  pauseTimer();

  if (isWork) {
    time = 5 * 60;
    modeDisplay.textContent = "Break Time";
  } else {
    time = 25 * 60;
    modeDisplay.textContent = "Work Time";
  }

  isWork = !isWork;
  updateDisplay();

  startTimer();
}

// init
updateDisplay();