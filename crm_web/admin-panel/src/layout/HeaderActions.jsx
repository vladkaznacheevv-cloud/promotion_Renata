import { NavLink } from "react-router-dom";

import Button from "../components/ui/Button";
import { RU } from "../i18n/ru";

export default function HeaderActions({ items = [], onLogout }) {
  return (
    <div className="flex w-full items-center justify-end gap-2 overflow-x-auto py-0.5 lg:w-auto lg:overflow-visible">
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} className="shrink-0">
          <Button variant="secondary" className="h-10 whitespace-nowrap px-3.5">
            {item.label}
          </Button>
        </NavLink>
      ))}
      <Button
        variant="danger"
        onClick={onLogout}
        className="h-10 shrink-0 whitespace-nowrap border-red-600 bg-red-600 px-3.5 text-white hover:bg-red-700 hover:text-white"
      >
        {RU.buttons.logout}
      </Button>
    </div>
  );
}
