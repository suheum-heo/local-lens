"use client";

import { useEffect, useMemo } from "react";
import {
  Circle,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { Restaurant } from "@/lib/types";
import type { SearchAreaView } from "@/lib/mapAreas";
import {
  STATUS,
  statusFromCoverage,
  statusFromLabel,
  type StatusKey,
} from "@/lib/statusStyles";
import "leaflet/dist/leaflet.css";

interface ResultsMapProps {
  areas: SearchAreaView[];
  restaurants: Restaurant[];
  selectedRestaurantId: string | null;
  onSelectRestaurant: (restaurantId: string) => void;
  className?: string;
}

function markerTone(r: Restaurant): StatusKey {
  if (r.label) return statusFromLabel(r.label);
  if (!r.match.matched) return "unmatched";
  return statusFromCoverage(r.rating_coverage);
}

function areaIcon() {
  return L.divIcon({
    className: "ll-area-marker",
    html: `<span style="
      display:block;width:10px;height:10px;border-radius:9999px;
      background:#22C55E;border:2px solid #fff;
      box-shadow:0 2px 8px rgba(17,24,39,.25);
    "></span>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });
}

function restaurantIcon(tone: StatusKey, selected: boolean) {
  const color = STATUS[tone].hex;
  if (selected) {
    return L.divIcon({
      className: "ll-restaurant-marker",
      html: `<span style="
        display:flex;align-items:center;justify-content:center;
        width:30px;height:30px;border-radius:9999px;
        background:${color};border:3px solid #fff;
        box-shadow:0 6px 18px ${color}88;
        transform:translateY(-2px);
      "><span style="width:8px;height:8px;border-radius:9999px;background:#fff;"></span></span>`,
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });
  }
  return L.divIcon({
    className: "ll-restaurant-marker",
    html: `<span style="
      display:block;width:14px;height:14px;border-radius:9999px;
      background:${color};border:2px solid #fff;
      box-shadow:0 2px 8px rgba(17,24,39,.28);opacity:.95;
    "></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function FitAndFocus({
  areas,
  restaurants,
  selectedRestaurantId,
}: {
  areas: SearchAreaView[];
  restaurants: Restaurant[];
  selectedRestaurantId: string | null;
}) {
  const map = useMap();

  useEffect(() => {
    const points: L.LatLngExpression[] = [
      ...areas.map((a) => [a.latitude, a.longitude] as L.LatLngExpression),
      ...restaurants.map(
        (r) => [r.latitude, r.longitude] as L.LatLngExpression,
      ),
    ];
    if (points.length === 0) return;
    map.invalidateSize();
    if (points.length === 1) {
      map.setView(points[0], 15);
      return;
    }
    const bounds = L.latLngBounds(points);
    map.fitBounds(bounds.pad(0.18));
  }, [map, areas, restaurants]);

  useEffect(() => {
    if (!selectedRestaurantId) return;
    const r = restaurants.find((x) => x.restaurant_id === selectedRestaurantId);
    if (!r) return;
    map.flyTo([r.latitude, r.longitude], Math.max(map.getZoom(), 16), {
      duration: 0.5,
    });
  }, [map, restaurants, selectedRestaurantId]);

  return null;
}

const LEGEND: { key: StatusKey; label: string }[] = [
  { key: "consensus", label: "양쪽 검증" },
  { key: "global", label: "Google" },
  { key: "local", label: "Kakao" },
  { key: "limited", label: "데이터 부족" },
];

export function ResultsMap({
  areas,
  restaurants,
  selectedRestaurantId,
  onSelectRestaurant,
  className,
}: ResultsMapProps) {
  const center = useMemo<[number, number]>(() => {
    if (areas.length > 0) {
      return [areas[0].latitude, areas[0].longitude];
    }
    if (restaurants.length > 0) {
      return [restaurants[0].latitude, restaurants[0].longitude];
    }
    return [37.5665, 126.978];
  }, [areas, restaurants]);

  return (
    <div
      className={`ll-map-shell relative h-full w-full overflow-hidden rounded-card border border-line bg-mist shadow-soft ${className ?? ""}`}
    >
      <MapContainer
        center={center}
        zoom={14}
        className="h-full w-full"
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <FitAndFocus
          areas={areas}
          restaurants={restaurants}
          selectedRestaurantId={selectedRestaurantId}
        />
        {areas.map((area) => (
          <Circle
            key={`circle-${area.id}`}
            center={[area.latitude, area.longitude]}
            radius={area.radius_m}
            pathOptions={{
              color: "#22C55E",
              fillColor: "#22C55E",
              fillOpacity: 0.06,
              weight: 1.25,
            }}
          />
        ))}
        {areas.map((area) => (
          <Marker
            key={`area-${area.id}`}
            position={[area.latitude, area.longitude]}
            icon={areaIcon()}
          >
            <Popup>
              <div className="font-semibold text-ink">{area.name}</div>
              <div className="mt-0.5 text-xs text-mute">
                반경{" "}
                {(area.radius_m / 1000).toFixed(
                  area.radius_m % 1000 === 0 ? 0 : 1,
                )}{" "}
                km
              </div>
            </Popup>
          </Marker>
        ))}
        {restaurants.map((r) => {
          const selected = r.restaurant_id === selectedRestaurantId;
          const tone = markerTone(r);
          return (
            <Marker
              key={r.restaurant_id}
              position={[r.latitude, r.longitude]}
              icon={restaurantIcon(tone, selected)}
              eventHandlers={{
                click: () => onSelectRestaurant(r.restaurant_id),
              }}
              zIndexOffset={selected ? 1000 : 0}
            >
              <Popup>
                <button
                  type="button"
                  className="text-left font-semibold text-ink hover:text-brand"
                  onClick={() => onSelectRestaurant(r.restaurant_id)}
                >
                  {r.name}
                </button>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {restaurants.length > 0 ? (
        <div className="ll-map-legend absolute bottom-3 right-3 z-[500] rounded-2xl bg-white/95 px-3 py-2 shadow-soft ring-1 ring-line backdrop-blur">
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            {LEGEND.map((item) => (
              <div
                key={item.key}
                className="flex items-center gap-1.5 text-[11px] font-medium text-ink/70"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: STATUS[item.key].hex }}
                />
                {item.label}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
