import type { RouteObject } from "react-router";
import { Customers } from "./Customers";
import { Products } from "./Products";
import { Plans } from "./Plans";
import "./catalog.css";

export function getRoutes(): RouteObject[] {
  return [
    { path: "/customers", element: <Customers /> },
    { path: "/catalog/products", element: <Products /> },
    { path: "/catalog/plans", element: <Plans /> },
  ];
}
