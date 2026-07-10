/**
 * Grahame Park — CF Project 4610 Reference Data
 *
 * Real Community Fibre deployment data for the "Compare with CF" toggle.
 * 15 buildings across 3 chains in the NW9 postcode area.
 */

export const GRAHAME_PARK_REFERENCE = {
  project: "CF Project 4610",
  area: "Grahame Park Estate, Colindale, NW9",
  buildings: [
    { name: "Napier", splitter: "64-way", dwellings: 42, joint_id: "J2100" },
    { name: "Norris", splitter: "64-way", dwellings: 47, joint_id: "J2101" },
    { name: "Orde", splitter: "32-way", dwellings: 18, joint_id: "J2102" },
    { name: "Roe", splitter: "32-way", dwellings: 19, joint_id: "J2103" },
    { name: "Slatter", splitter: "32-way", dwellings: 22, joint_id: "J2104" },
    { name: "Tedder", splitter: "64-way", dwellings: 46, joint_id: "J2105" },
    { name: "Sassoon", splitter: "64-way", dwellings: 16, joint_id: "J2106" },
    { name: "Saimet", splitter: "PBO", dwellings: 18, feeder: "Sassoon" },
    { name: "Sopwith", splitter: "64-way", dwellings: 16, joint_id: "J2108" },
    { name: "Spitfire", splitter: "PBO", dwellings: 18, feeder: "Sopwith" },
    { name: "Rapide", splitter: "32-way", dwellings: 24, joint_id: "J2110" },
    { name: "Ratier", splitter: "32-way", dwellings: 24, joint_id: "J2111" },
    { name: "Wilshire", splitter: "32-way", dwellings: 20, joint_id: "J2112" },
    { name: "Whittle", splitter: "PBO", dwellings: 24, feeder: "Tedder" },
    { name: "Wheeler", splitter: "32-way", dwellings: 24, joint_id: "J2114" },
  ],
  cables: [
    { id: "FC2100", from: "AUX", to: "Napier", length_m: 189, spec: "144F" },
    { id: "FC2101", from: "Napier", to: "Norris", length_m: 78, spec: "144F" },
    { id: "FC2102", from: "Norris", to: "Orde", length_m: 65, spec: "48F" },
    { id: "FC2103", from: "Orde", to: "Roe", length_m: 42, spec: "24F" },
    { id: "FC2104", from: "Roe", to: "Slatter", length_m: 53, spec: "24F" },
    { id: "FC2105", from: "AUX", to: "Tedder", length_m: 210, spec: "144F" },
    { id: "FC2106", from: "Tedder", to: "Sassoon", length_m: 92, spec: "48F" },
    { id: "FC2107", from: "Sassoon", to: "Saimet", length_m: 34, spec: "12F" },
    { id: "FC2108", from: "Tedder", to: "Sopwith", length_m: 85, spec: "48F" },
    { id: "FC2109", from: "Sopwith", to: "Spitfire", length_m: 38, spec: "12F" },
    { id: "FC2110", from: "Tedder", to: "Whittle", length_m: 110, spec: "12F" },
    { id: "FC2111", from: "AUX", to: "Wheeler", length_m: 175, spec: "144F" },
    { id: "FC2112", from: "Wheeler", to: "Rapide", length_m: 68, spec: "48F" },
    { id: "FC2113", from: "Rapide", to: "Ratier", length_m: 55, spec: "24F" },
    { id: "FC2114", from: "Ratier", to: "Wilshire", length_m: 47, spec: "24F" },
    { id: "FC2115", from: "Norris", to: "Slatter", length_m: 60, spec: "48F" },
  ],
  branches: ["Wheeler Chain", "Slatter Chain", "Norris Chain"],
  totals: {
    premises: 364,
    buildings: 15,
    splitters_32way: 7,
    splitters_64way: 5,
    pbo_count: 3,
  },
} as const;
