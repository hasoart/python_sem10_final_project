const API_BASE_URL = "http://localhost:8000";

const uploadForm = document.querySelector("#upload-form");
const photoInput = document.querySelector("#photo-input");
const uploadStatus = document.querySelector("#upload-status");
const photoIdsTextarea = document.querySelector("#photo-ids");
const clearPhotosButton = document.querySelector("#clear-photos");
const createTaskButton = document.querySelector("#create-task");
const taskIdInput = document.querySelector("#task-id");
const taskResponse = document.querySelector("#task-response");
const openResultsButton = document.querySelector("#open-results");

const photoIds = [];

function renderPhotoIds() {
  photoIdsTextarea.value = photoIds.join("\n");
}

async function uploadPhoto(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/photos`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Upload failed for ${file.name}: ${response.status} ${errorText}`);
  }

  return response.json();
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const files = Array.from(photoInput.files);
  if (files.length === 0) {
    uploadStatus.textContent = "Выбери хотя бы один файл.";
    return;
  }

  uploadStatus.textContent = "Загрузка...";

  try {
    for (const file of files) {
      const result = await uploadPhoto(file);
      photoIds.push(result.photo_id);
      renderPhotoIds();
    }

    uploadStatus.textContent = `Загружено файлов: ${files.length}`;
    photoInput.value = "";
  } catch (error) {
    uploadStatus.textContent = error.message;
  }
});

clearPhotosButton.addEventListener("click", () => {
  photoIds.length = 0;
  renderPhotoIds();
});

createTaskButton.addEventListener("click", async () => {
  if (photoIds.length === 0) {
    taskResponse.textContent = "Сначала загрузи фотографии.";
    return;
  }

  taskResponse.textContent = "Создание task...";

  try {
    const response = await fetch(`${API_BASE_URL}/tasks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ photo_ids: photoIds }),
    });

    const result = await response.json();
    taskResponse.textContent = JSON.stringify(result, null, 2);

    if (!response.ok) {
      throw new Error(`Task creation failed: ${response.status}`);
    }

    taskIdInput.value = result.task_id;
    openResultsButton.disabled = false;
  } catch (error) {
    taskResponse.textContent += `\n\n${error.message}`;
  }
});

openResultsButton.addEventListener("click", () => {
  const taskId = taskIdInput.value.trim();
  if (taskId) {
    window.location.href = `./results.html?task_id=${encodeURIComponent(taskId)}`;
  }
});
