// ============================================
// EMBER — вся логика WebApp
// ============================================

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  try { document.body.style.background = tg.themeParams?.bg_color || ""; } catch (e) {}
}

// ============ ОБЩЕЕ ============

const STORAGE_KEY = "ember_form_data";

function loadFormData() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : {};
  } catch (e) { return {}; }
}

const profile = {
  name: "", username: "", age: 18, looking_for: "", gender: "",
  city: "", bio: "", photo_id: "",
  ...loadFormData(),
};

function saveFormData() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch (e) {}
}

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

function showError(text) {
  if (tg && tg.showAlert) tg.showAlert(text);
  else alert(text);
}

function haptic(type = "light") {
  if (tg && tg.HapticFeedback) {
    if (type === "light") tg.HapticFeedback.impactOccurred("light");
    if (type === "medium") tg.HapticFeedback.impactOccurred("medium");
    if (type === "success") tg.HapticFeedback.notificationOccurred("success");
    if (type === "error") tg.HapticFeedback.notificationOccurred("error");
  }
}

// ============ API ХЕЛПЕР ============

async function apiCall(path, extra = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      initData: tg?.initData || "",
      ...extra,
    }),
  });
  return await response.json();
}

// ============================================
// ЭКРАН 1: ИМЯ
// ============================================
document.getElementById("input-name").value = profile.name || "";
document.getElementById("input-username").value = profile.username ? "@" + profile.username : "";

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
  saveFormData();
  haptic("light");
  showScreen("screen-age");
});

// ============================================
// ЭКРАН 2: ВОЗРАСТ
// ============================================
const ageInput = document.getElementById("input-age");
const ageValue = document.getElementById("age-value");

ageInput.value = profile.age || 18;
ageValue.textContent = profile.age || 18;

ageInput.addEventListener("input", () => {
  ageValue.textContent = ageInput.value;
  profile.age = parseInt(ageInput.value);
  saveFormData();
  ageValue.classList.add("bump");
  setTimeout(() => ageValue.classList.remove("bump"), 150);
  haptic("light");
});

document.querySelectorAll("#looking-chips .chip").forEach(chip => {
  if (chip.dataset.value === profile.looking_for) chip.classList.add("selected");
  chip.addEventListener("click", () => {
    document.querySelectorAll("#looking-chips .chip").forEach(c => c.classList.remove("selected"));
    chip.classList.add("selected");
    profile.looking_for = chip.dataset.value;
    saveFormData();
    haptic("light");
  });
});

document.getElementById("btn-next-2").addEventListener("click", () => {
  if (!profile.looking_for) {
    haptic("error"); showError("Выбери, кого ищешь"); return;
  }
  haptic("light"); showScreen("screen-gender");
});

// ============================================
// ЭКРАН 3: ПОЛ
// ============================================
document.querySelectorAll("#gender-chips .chip").forEach(chip => {
  if (chip.dataset.value === profile.gender) chip.classList.add("selected");
  chip.addEventListener("click", () => {
    document.querySelectorAll("#gender-chips .chip").forEach(c => c.classList.remove("selected"));
    chip.classList.add("selected");
    profile.gender = chip.dataset.value;
    saveFormData();
    haptic("light");
  });
});

document.getElementById("btn-next-3").addEventListener("click", () => {
  if (!profile.gender) {
    haptic("error"); showError("Выбери, кто ты"); return;
  }
  haptic("light"); showScreen("screen-city");
});

// ============================================
// ЭКРАН 4: ГОРОД
// ============================================
document.getElementById("input-city").value = profile.city || "";

document.getElementById("btn-next-4").addEventListener("click", () => {
  const city = document.getElementById("input-city").value.trim();
  if (city.length < 2) {
    haptic("error"); showError("Укажи город"); return;
  }
  profile.city = city;
  saveFormData();
  haptic("light"); showScreen("screen-bio");
});

// ============================================
// ЭКРАН 5: О СЕБЕ
// ============================================
document.getElementById("input-bio").value = profile.bio || "";

document.getElementById("btn-next-5").addEventListener("click", () => {
  const bio = document.getElementById("input-bio").value.trim();
  if (bio.length < 5) {
    haptic("error"); showError("Напиши хотя бы пару слов о себе"); return;
  }
  profile.bio = bio;
  saveFormData();
  haptic("light");
  showScreen("screen-photo");
  checkPhoto();
});

// ============================================
// ЭКРАН 6: ФОТО
// ============================================
function checkPhoto() {
  const urlParams = new URLSearchParams(window.location.search);
  const urlPhotoId = urlParams.get("photo_id");
  if (urlPhotoId) {
    localStorage.setItem("ember_photo_id", urlPhotoId);
    profile.photo_id = urlPhotoId;
    saveFormData();
    document.getElementById("photo-status").textContent = "✅ Фото загружено";
    document.getElementById("btn-save").disabled = false;
    window.history.replaceState({}, "", window.location.pathname);
    return;
  }
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

setInterval(() => {
  const photoScreen = document.getElementById("screen-photo");
  if (photoScreen && photoScreen.classList.contains("active")) checkPhoto();
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
      body: JSON.stringify({ initData: tg?.initData || "", profile: profile }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Ошибка сервера");

    localStorage.removeItem("ember_photo_id");
    localStorage.removeItem(STORAGE_KEY);
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
  if (tg && tg.close) tg.close(); else window.close();
});

// ============================================
// ЛЕНТА (FEED)
// ============================================

let currentProfile = null;

async function loadNextProfile() {
  document.getElementById("loading-feed").style.display = "block";
  document.getElementById("card").style.display = "none";
  document.getElementById("feed-actions").style.display = "none";
  document.getElementById("empty-feed").style.display = "none";

  try {
    const data = await apiCall("/api/feed");
    if (!data.profile) {
      document.getElementById("loading-feed").style.display = "none";
      document.getElementById("empty-feed").style.display = "block";
      return;
    }
    currentProfile = data.profile;
    showCard(currentProfile);
  } catch (err) {
    document.getElementById("loading-feed").style.display = "none";
    document.getElementById("empty-feed").style.display = "block";
  }
}

function showCard(p) {
  document.getElementById("loading-feed").style.display = "none";
  document.getElementById("card").style.display = "block";
  document.getElementById("feed-actions").style.display = "flex";

  document.getElementById("card-img").src = `/api/photo/${p.photo_id}`;
  document.getElementById("card-name").textContent = p.name;
  document.getElementById("card-age").textContent = p.age;
  document.getElementById("card-city").textContent = p.city;
  document.getElementById("card-bio").textContent = p.bio;

  // Значки
  const badges = document.getElementById("card-badges");
  badges.innerHTML = "";
  if (p.is_verified) {
    const b = document.createElement("span");
    b.className = "badge verified";
    b.textContent = "✓";
    badges.appendChild(b);
  }
  if (p.is_premium) {
    const b = document.createElement("span");
    b.className = "badge premium";
    b.textContent = "⭐";
    badges.appendChild(b);
  }

  // Анимация появления
  const card = document.getElementById("card");
  card.classList.remove("swiping-left", "swiping-right");
}

async function likeCurrent() {
  if (!currentProfile) return;
  const card = document.getElementById("card");
  card.classList.add("swiping-right");
  haptic("success");

  try {
    const data = await apiCall("/api/like", { to_id: currentProfile.user_id });
    setTimeout(async () => {
      if (data.match) {
        document.getElementById("match-text").textContent = `Вы с ${currentProfile.name} лайкнули друг друга!`;
        showScreen("screen-match");
      } else {
        await loadNextProfile();
      }
    }, 400);
  } catch (err) {
    console.error(err);
    setTimeout(loadNextProfile, 400);
  }
}

async function skipCurrent() {
  if (!currentProfile) return;
  const card = document.getElementById("card");
  card.classList.add("swiping-left");
  haptic("light");

  try {
    await apiCall("/api/skip", { to_id: currentProfile.user_id });
  } catch (err) { console.error(err); }

  setTimeout(loadNextProfile, 400);
}

document.getElementById("btn-like").addEventListener("click", likeCurrent);
document.getElementById("btn-skip").addEventListener("click", skipCurrent);
document.getElementById("btn-back-menu").addEventListener("click", () => {
  if (tg && tg.close) tg.close(); else window.close();
});
document.getElementById("btn-match-next").addEventListener("click", () => {
  showScreen("screen-feed");
  loadNextProfile();
});

// ============================================
// МЭТЧИ (список)
// ============================================

async function loadMatches() {
  const list = document.getElementById("matches-list");
  const empty = document.getElementById("empty-matches");
  list.innerHTML = "";
  empty.style.display = "none";

  try {
    const data = await apiCall("/api/matches");
    const matches = data.matches || [];
    if (matches.length === 0) {
      empty.style.display = "block";
      return;
    }
    matches.forEach(m => {
      const a = document.createElement("a");
      a.className = "match-item";
      a.href = m.username ? `https://t.me/${m.username}` : "#";
      if (!m.username) a.style.pointerEvents = "none";
      a.target = "_blank";
      a.innerHTML = `
        <img src="/api/photo/${m.photo_id}" alt="${m.name}">
        <div class="match-name">${m.name}</div>
      `;
      list.appendChild(a);
    });
  } catch (err) {
    empty.style.display = "block";
  }
}

document.getElementById("btn-matches-back").addEventListener("click", () => {
  if (tg && tg.close) tg.close(); else window.close();
});

// ============================================
// СТАРТ — определяем, куда идти
// ============================================

const startParams = new URLSearchParams(window.location.search);
const hasPhotoInUrl = startParams.get("photo_id");
const wantFeed = startParams.get("screen") === "feed";

(async () => {
  if (hasPhotoInUrl) {
    showScreen("screen-photo");
    checkPhoto();
    return;
  }

  if (profile.photo_id) {
    // Уже зарегистрирован → лента
    showScreen("screen-feed");
    loadNextProfile();
    return;
  }

  if (profile.name) {
    showScreen("screen-photo");
    checkPhoto();
    return;
  }

  // Новый юзер
  showScreen("screen-name");
})();
