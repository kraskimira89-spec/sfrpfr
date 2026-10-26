"use client";

/** Кнопки «Скачать» / «Загрузить исправленный» у сгенерированных артефактов. */

type Props = {
  busy?: boolean;
  downloadLabel?: string;
  uploadLabel?: string;
  downloadDisabled?: boolean;
  uploadDisabled?: boolean;
  accept?: string;
  downloadTitle?: string;
  uploadTitle?: string;
  onDownload?: () => void;
  onUploadFile?: (file: File) => void;
};

export function GeneratedDocActions({
  busy = false,
  downloadLabel = "Скачать",
  uploadLabel = "Загрузить исправленный",
  downloadDisabled = false,
  uploadDisabled = false,
  accept = ".pdf,.doc,.docx,.txt,.csv,application/pdf,text/plain,text/csv",
  downloadTitle,
  uploadTitle,
  onDownload,
  onUploadFile,
}: Props) {
  return (
    <div className="row-actions">
      {onDownload ? (
        <button
          type="button"
          className="secondary"
          disabled={busy || downloadDisabled}
          title={downloadTitle || downloadLabel}
          onClick={() => onDownload()}
        >
          {downloadLabel}
        </button>
      ) : null}
      {onUploadFile ? (
        <label
          className="secondary"
          style={{ cursor: busy || uploadDisabled ? "wait" : "pointer" }}
          title={uploadTitle || uploadLabel}
        >
          {uploadLabel}
          <input
            type="file"
            accept={accept}
            hidden
            disabled={busy || uploadDisabled}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) onUploadFile(file);
            }}
          />
        </label>
      ) : null}
    </div>
  );
}
