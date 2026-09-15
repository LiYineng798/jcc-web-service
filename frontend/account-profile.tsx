import React from "react";
import { createRoot } from "react-dom/client";
import BentoCard from "@/components/ui/bento-card";
import "./account-ui.css";

const root = document.getElementById("accountApp");
if (root)
  createRoot(root).render(<BentoCard />);
