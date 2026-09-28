// ============================================
// EMBER — логика WebApp
// ============================================

// ===== Инициализация Telegram WebApp =====
const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  try {
    document.body.style.background = tg.themeParams?.bg_color || "";
  } catch (e) {}
}

// ===== Данные анкеты =====
const profile = {
  name: "",
  username: "",
  age: 18,
  looking_for: "",
  gender: "",
  city: "",
  bio: "",
  photo_id: "",
};

// ===== Переключение экранов с анимацией =====
function showScreen(id) {
  const current = document.querySelector(".screen.active");
  const next = document.getElementById(id);
  if (!next || current === next) return;

  if (current) {
    current.style.opacity = "0";
    current.style.transform = "translateX(-24px)";
    setTimeout(() => {
      current.classList.remove("active");
      current.style.opacity = "";
      current.style.transform = "";
    }, 200);
  }

  setTimeout(() => {
    next.classList.add("active");
    next.style.opacity = "";
    next.style.transform = "";
  }, 200);

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ===== Показать ошибку =====
function showError(text) {
  if (tg && tg.showAlert) {
    tg.showAlert(text);
  } else {
    alert(text);
  }
}

// ===== Вибро-отклик =====
function haptic(type = "light") {
  if (tg && tg.HapticFeedback) {
    if (type === "light") tg.HapticFeedback.impactOccurred("light");
    if (type === "medium") tg.HapticFeedback.impactOccurred("medium");
    if (type === "success") tg.HapticFeedback.notificationOccurred("success");
    if (type === "error") tg.HapticFeedback.notificationOccurred("error");
  }
}

// ============================================
// ЭКРАН 1: ИМЯ
// ============================================
document.getElementById("btn-next-1").addEventListener("click", () => {
  const name = document.getElementById("input-name").value.trim();
  const username = document.getElementById("input-username").value.trim().replace("@", "");

  if (name.length < 2 || name.length > 32) {
    haptic("error");
    showError("Имя должно быть от 2 до 32 символов");
    return;
  }

  profile.name = name;
  profile.username = username;
  haptic("light");
  showScreen("screen-age");
});

// ============================================
// ЭКРАН 2: ВОЗРАСТ + КОГО ИЩЕШЬ
// ============================================
const ageInput = document.getElementById("input-age");
const ageValue = document.getElementById("age-value");

ageInput.addEventListener("input", () => {
  ageValue.textContent = ageInput.value;
  profile.age = parseInt(ageInput.value);
  ageValue.classList.add("bump");
  setTimeout(() => ageValue.classList.remove("bump"), 150);
  haptic("light");
});

document.querySelectorAll("#looking-chips .chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll("#looking-chips .chip").forEach(c => c.classList.remove("selected"));
    chip.classList.add("selected");
    profile.looking_for = chip.dataset.value;
    haptic("light");
  });
});

document.getElementById("btn-next-2").addEventListener("click", () => {
  if (!profile.looking_for) {
    haptic("error");
    showError("Выбери, кого ищешь");
    return;
  }
  haptic("light");
  showScreen("screen-gender");
});

// ============================================
// ЭКРАН 3: ПОЛ
// ============================================
document.querySelectorAll("#gender-chips .chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll("#gender-chips .chip").forEach(c => c.classList.remove("selected"));
    chip.classList.add("selected");
    profile.gender = chip.dataset.value;
    haptic("light");
  });
});

document.getElementById("btn-next-3").addEventListener("click", () => {
  if (!profile.gender) {
    haptic("error");
    showError("Выбери, кто ты");
    return;
  }
  haptic("light");
  showScreen("screen-city");
});

// ============================================
// ЭКРАН 4: ГОРОД
// ============================================
document.getElementById("btn-next-4").addEventListener("click", () => {
  const city = document.getElementById("input-city").value.trim();
  if (city.length < 2) {
    haptic("error");
    showError("Укажи город");
    return;
  }
  profile.city = city;
  haptic("light");
  showScreen("screen-bio");
});

// ============================================
// ЭКРАН 5: О СЕБЕ
// ============================================
document.getElementById("btn-next-5").addEventListener("click", () => {
  const bio = document.getElementById("input-bio").value.trim();
  if (bio.length < 5) {
    haptic("error");
    showError("Напиши хотя бы пару слов о себе");
    return;
  }
  profile.bio = bio;
  haptic("light");
  showScreen("screen-photo");
  checkPhoto();
});

// ============================================
// ЭКРАН 6: ФОТО
// ============================================
function checkPhoto() {
  // 1. Приоритет — photo_id из URL (deep link от бота)
  const urlParams = new URLSearchParams(window.location.search);
  const urlPhotoId = urlParams.get("photo_id");

  if (urlPhotoId) {
    localStorage.setItem("ember_photo_id", urlPhotoId);
    profile.photo_id = urlPhotoId;
    document.getElementById("photo-status").textContent = "✅ Фото загружено";
    document.getElementById("btn-save").disabled = false;

    // Убираем photo_id из URL, чтобы не мешал
    window.history.replaceState({}, "", window.location.pathname);
    return;
  }

  // 2. Иначе — проверяем localStorage
  const savedPhoto = localStorage.getItem("ember_photo_id");
  if (savedPhoto) {
    profile.photo_id = savedPhoto;
    document.getElementById("photo-status").textContent = "✅ Фото загружено";
    document.getElementById("btn-save").disabled = false;
  } else {
    document.getElementById("photo-status").textContent = "⏳ Фото ещё не загружено";
    document.getElementById("btn-save").disabled = true;
  }
}

// Проверяем фото каждые 2 секунды, пока открыт экран
setInterval(() => {
  const photoScreen = document.getElementById("screen-photo");
  if (photoScreen && photoScreen.classList.contains("active")) {
    checkPhoto();
  }
}, 2000);

// ============================================
// СОХРАНЕНИЕ АНКЕТЫ
// ============================================
document.getElementById("btn-save").addEventListener("click", async () => {
  const btn = document.getElementById("btn-save");
  btn.disabled = true;
  btn.textContent = "Сохраняем...";

  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        initData: tg?.initData || "",
        profile: profile,
      }),
    });

    const data = await response.json();

    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Ошибка сервера");
    }

    localStorage.removeItem("ember_photo_id");
    haptic("success");
    showScreen("screen-done");
  } catch (err) {
    haptic("error");
    showError("Ошибка: " + err.message);
    btn.disabled = false;
    btn.textContent = "Сохранить анкету";
  }
});

// ============================================
// ЗАКРЫТИЕ
// ============================================
document.getElementById("btn-close").addEventListener("click", () => {
  haptic("light");
  if (tg && tg.close) {
    tg.close();
  } else {
    window.close();
  }
});

// ============================================
// СТАРТ
// ============================================
showScreen("screen-name");
