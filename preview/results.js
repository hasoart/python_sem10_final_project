const API_BASE_URL = "http://localhost:8000";

const taskIdInput = document.querySelector("#task-id");
const loadResultsButton = document.querySelector("#load-results");
const statusText = document.querySelector("#status");
const rawJson = document.querySelector("#raw-json");
const previews = document.querySelector("#previews");

const params = new URLSearchParams(window.location.search);
const initialTaskId = params.get("task_id");

if (initialTaskId) {
  taskIdInput.value = initialTaskId;
}

function renderPreviews(result) {
  previews.innerHTML = "";

  for (const photo of result.photos || []) {
    const card = document.createElement("div");
    card.className = "preview-card";

    const title = document.createElement("h3");
    title.textContent = photo.original_filename;

    const meta = document.createElement("p");
    meta.textContent = `photo_id: ${photo.photo_id}`;

    card.append(title, meta);

    if (photo.preview_url) {
      const image = document.createElement("img");
      image.src = `${API_BASE_URL}${photo.preview_url}`;
      image.alt = `Preview for ${photo.original_filename}`;
      card.append(image);
    } else {
      const empty = document.createElement("p");
      empty.textContent = "Preview пока недоступен.";
      card.append(empty);
    }

    previews.append(card);
  }
}

async function loadResults() {
  const taskId = taskIdInput.value.trim();
  if (!taskId) {
    statusText.textContent = "Укажи task_id.";
    return;
  }

  statusText.textContent = "Загрузка...";
  rawJson.textContent = "";
  previews.innerHTML = "";

  try {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/results`);
    const text = await response.text();

    let result;
    try {
      result = JSON.parse(text);
      rawJson.textContent = JSON.stringify(result, null, 2);
    } catch {
      rawJson.textContent = text;
    }

    if (response.status === 202) {
      statusText.textContent = "Task еще обрабатывается. Повтори запрос позже.";
      return;
    }

    if (!response.ok) {
      statusText.textContent = `Ошибка: ${response.status}`;
      return;
    }

    statusText.textContent = "Готово.";
    renderPreviews(result);
  } catch (error) {
    statusText.textContent = error.message;
  }
}

loadResultsButton.addEventListener("click", loadResults);

if (initialTaskId) {
  loadResults();
}
