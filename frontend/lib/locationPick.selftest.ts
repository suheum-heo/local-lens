import type { LocationCatalogItem } from "./types";
import { resolveLocationPick } from "./locationPick";

function station(
  id: string,
  name: string,
  city: LocationCatalogItem["city"] = "seoul",
): LocationCatalogItem {
  return {
    id,
    name,
    name_en: null,
    city,
    latitude: 37.5,
    longitude: 127.0,
    mode: "station",
    default_radius_m: 1000,
  };
}

const JAMSIL = [
  station("jamsil", "잠실역"),
  station("saenae", "잠실새내역"),
  station("naru", "잠실나루역"),
];

function assert(cond: unknown, msg: string): void {
  if (!cond) throw new Error(msg);
}

assert(resolveLocationPick("잠실", JAMSIL) === null, "잠실 must not auto-pick 잠실역");
assert(
  resolveLocationPick("잠실역", JAMSIL)?.id === "jamsil",
  "잠실역 fully typed selects 잠실역",
);
assert(
  resolveLocationPick("잠실새내", JAMSIL)?.id === "saenae",
  "잠실새내 selects 잠실새내역",
);
assert(
  resolveLocationPick("잠실새내역", JAMSIL)?.id === "saenae",
  "잠실새내역 fully typed selects itself",
);
assert(
  resolveLocationPick("지행", [station("jihaeng", "지행역")])?.id === "jihaeng",
  "unique stem still auto-selects",
);

console.log("locationPick.selftest: ok");
