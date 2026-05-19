const MSK_TZ = "Europe/Moscow";

const MINUTES_FMT = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MSK_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const SECONDS_FMT = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MSK_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function formatMskMinutes(iso: string | null | undefined): string {
  if (!iso) return "—";
  return MINUTES_FMT.format(new Date(iso));
}

export function formatMskSeconds(iso: string | null | undefined): string {
  if (!iso) return "—";
  return SECONDS_FMT.format(new Date(iso));
}
