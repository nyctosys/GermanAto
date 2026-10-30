"use client";

import { useState } from "react";
import { Input, Select } from "@/components/ui";

const COUNTRIES: { code: string; name: string }[] = [
  { code: "92", name: "Pakistan" }, { code: "971", name: "UAE" }, { code: "966", name: "Saudi Arabia" }, { code: "974", name: "Qatar" },
  { code: "968", name: "Oman" }, { code: "965", name: "Kuwait" }, { code: "973", name: "Bahrain" }, { code: "93", name: "Afghanistan" },
  { code: "91", name: "India" }, { code: "880", name: "Bangladesh" }, { code: "98", name: "Iran" }, { code: "90", name: "Turkey" },
  { code: "44", name: "United Kingdom" }, { code: "1", name: "USA / Canada" }, { code: "49", name: "Germany" }, { code: "86", name: "China" },
  { code: "60", name: "Malaysia" },
];

/** Pakistani mobiles read 300 1234567; others in groups of three. */
function group(cc: string, d: string) {
  if (cc === "92") return [d.slice(0, 3), d.slice(3, 10)].filter(Boolean).join(" ");
  return (d.match(/\d{1,3}/g) ?? []).join(" ");
}

function split(v: string): { cc: string; digits: string } {
  const d = (v ?? "").replace(/[^\d+]/g, "");
  if (d.startsWith("+")) {
    const hit = [...COUNTRIES].sort((a, b) => b.code.length - a.code.length).find((c) => d.slice(1).startsWith(c.code));
    if (hit) return { cc: hit.code, digits: d.slice(1 + hit.code.length) };
  }
  return { cc: "92", digits: d.replace(/^\+?(92)?0?/, "") };
}

/** Country code and number are two controls; the number formats itself as it is typed. Posts +CCNUMBER under `name`. */
export function PhoneInput({ name, defaultValue = "", required, placeholder = "300 1234567" }:
  { name: string; defaultValue?: string; required?: boolean; placeholder?: string }) {
  const start = split(defaultValue);
  const [cc, setCc] = useState(start.cc);
  const [digits, setDigits] = useState(start.digits.replace(/\D/g, ""));
  const codes = COUNTRIES.some((c) => c.code === cc) ? COUNTRIES : [{ code: cc, name: "Other" }, ...COUNTRIES];
  const max = cc === "92" ? 10 : 12;

  return (
    <div className="flex gap-2">
      <div className="w-36 shrink-0">
        <Select aria-label={`${name}, country code`} value={cc} onChange={(e) => setCc(e.target.value)}>
          {codes.map((c) => <option key={c.code} value={c.code}>+{c.code} {c.name}</option>)}
        </Select>
      </div>
      <div className="min-w-0 flex-1">
        <Input aria-label={`${name}, number`} inputMode="tel" autoComplete="tel-national" required={required} placeholder={placeholder}
          value={group(cc, digits)}
          onChange={(e) => {
            let d = e.target.value.replace(/\D/g, "");
            if (cc === "92") d = d.replace(/^0+/, "").replace(/^92(?=\d{10})/, "");
            setDigits(d.slice(0, max));
          }} />
      </div>
      <input type="hidden" name={name} value={digits ? `+${cc}${digits}` : ""} />
    </div>
  );
}
