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
import "leaflet/dist/leaflet.css";

interface ResultsMapProps {
  areas: SearchAreaView[];
  restaurants: Restaurant[];
  selectedRestaurantId: string | null;
  onSelectRestaurant: (restaurantId: string) => void;
}

function areaIcon(active: boolean) {
  return L.divIcon({
    className: "ll-area-marker",
    html: `<span style="
      display:block;width:12px;height:12px;border-radius:9999px;
      background:${active ? "#2f6b4f" : "#1a1f1c"};
      border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.35);
    "></span>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

function restaurantIcon(selected: boolean) {
  const bg = selected ? "#c45c26" : "#2f6b4f";
  const size = selected ? 18 : 14;
  return L.divIcon({
    className: "ll-restaurant-marker",
    html: `<span style="
      display:block;width:${size}px;height:${size}px;border-radius:9999px;
      background:${bg};border:2px solid #fff;
      box-shadow:0 1px 4px rgba(0,0,0,.4);
    "></span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
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
    if (points.length === 1) {
      map.setView(points[0], 15);
      return;
    }
    const bounds = L.latLngBounds(points);
    map.fitBounds(bounds.pad(0.2));
  }, [map, areas, restaurants]);

  useEffect(() => {
    if (!selectedRestaurantId) return;
    const r = restaurants.find((x) => x.restaurant_id === selectedRestaurantId);
    if (!r) return;
    map.flyTo([r.latitude, r.longitude], Math.max(map.getZoom(), 16), {
      duration: 0.45,
    });
  }, [map, restaurants, selectedRestaurantId]);

  return null;
}

export function ResultsMap({
  areas,
  restaurants,
  selectedRestaurantId,
  onSelectRestaurant,
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
    <div className="h-64 w-full overflow-hidden border border-ink/10 sm:h-80">
      <MapContainer
        center={center}
        zoom={14}
        className="h-full w-full"
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
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
              color: "#2f6b4f",
              fillColor: "#2f6b4f",
              fillOpacity: 0.08,
              weight: 1.5,
            }}
          />
        ))}
        {areas.map((area) => (
          <Marker
            key={`area-${area.id}`}
            position={[area.latitude, area.longitude]}
            icon={areaIcon(true)}
          >
            <Popup>
              <span className="text-sm font-medium">{area.name}</span>
              <br />
              <span className="text-xs text-ink/60">
                반경 {(area.radius_m / 1000).toFixed(area.radius_m % 1000 === 0 ? 0 : 1)} km
              </span>
            </Popup>
          </Marker>
        ))}
        {restaurants.map((r) => {
          const selected = r.restaurant_id === selectedRestaurantId;
          return (
            <Marker
              key={r.restaurant_id}
              position={[r.latitude, r.longitude]}
              icon={restaurantIcon(selected)}
              eventHandlers={{
                click: () => onSelectRestaurant(r.restaurant_id),
              }}
              zIndexOffset={selected ? 1000 : 0}
            >
              <Popup>
                <button
                  type="button"
                  className="text-left text-sm font-medium text-ink"
                  onClick={() => onSelectRestaurant(r.restaurant_id)}
                >
                  {r.name}
                </button>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
