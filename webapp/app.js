const startParams = new URLSearchParams(window.location.search);
const hasPhotoInUrl = startParams.get("photo_id");
const wantFeed = startParams.get("screen") === "feed";

(async () => {
  // 1. photo_id в URL — на экран фото
  if (hasPhotoInUrl) {
    showScreen("screen-photo");
    checkPhoto();
    return;
  }

  // 2. Пришли с ?screen=feed — проверим через API, что юзер зарегистрирован
  if (wantFeed) {
    try {
      const data = await apiCall("/api/me");
      if (data && data.user_id) {
        showScreen("screen-feed");
        loadNextProfile();
        return;
      }
    } catch (e) {
      console.error("me check error:", e);
    }
    // Если не зарегистрирован — на форму регистрации
    showScreen("screen-name");
    return;
  }

  // 3. Локально есть photo_id — на ленту
  if (profile.photo_id) {
    showScreen("screen-feed");
    loadNextProfile();
    return;
  }

  // 4. Есть имя — на экран фото
  if (profile.name) {
    showScreen("screen-photo");
    checkPhoto();
    return;
  }

  // 5. Новый — на имя
  showScreen("screen-name");
})();
