(function () {
  const MAX_BYTES = 20 * 1024 * 1024;

  document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    if (!dropzone || !fileInput) return;

    const idle = document.getElementById('dropzoneIdle');
    const success = document.getElementById('dropzoneSuccess');
    const nameLabel = document.getElementById('selectedFileName');
    const checkmark = success.querySelector('.draw-checkmark');

    function showSelected(file) {
      if (!file) return;
      if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        window.Scholaris.showToast('Only PDF files are allowed.', 'error');
        fileInput.value = '';
        return;
      }
      if (file.size > MAX_BYTES) {
        window.Scholaris.showToast('File exceeds the 20MB limit.', 'error');
        fileInput.value = '';
        return;
      }
      nameLabel.textContent = file.name;
      idle.style.display = 'none';
      success.style.display = 'block';
      checkmark.classList.remove('drawn');
      requestAnimationFrame(() => requestAnimationFrame(() => checkmark.classList.add('drawn')));
    }

    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => showSelected(fileInput.files[0]));

    ['dragenter', 'dragover'].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });
    ['dragleave', 'dragend'].forEach((evt) => {
      dropzone.addEventListener(evt, () => dropzone.classList.remove('dragover'));
    });
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file) {
        fileInput.files = e.dataTransfer.files;
        showSelected(file);
      }
    });
  });
})();
