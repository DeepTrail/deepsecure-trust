"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  SsoLoginScene,
  ServiceConnectionScene,
  AgentRegistrationScene,
  DelegationScene,
  McpToolCallScene,
  AuditReviewScene,
} from "./scenes";
import type { DemoSceneProps } from "./scenes";
import { allScenes } from "@/data/demo";

type SceneComponent = React.ComponentType<DemoSceneProps>;

interface SceneEntry {
  id: string;
  title: string;
  description: string;
  Component: SceneComponent;
}

const SCENE_REGISTRY: SceneEntry[] = [
  { id: allScenes[0].sceneId, title: allScenes[0].title, description: allScenes[0].description, Component: SsoLoginScene },
  { id: allScenes[1].sceneId, title: allScenes[1].title, description: allScenes[1].description, Component: ServiceConnectionScene },
  { id: allScenes[2].sceneId, title: allScenes[2].title, description: allScenes[2].description, Component: AgentRegistrationScene },
  { id: allScenes[3].sceneId, title: allScenes[3].title, description: allScenes[3].description, Component: DelegationScene },
  { id: allScenes[4].sceneId, title: allScenes[4].title, description: allScenes[4].description, Component: McpToolCallScene },
  { id: allScenes[5].sceneId, title: allScenes[5].title, description: allScenes[5].description, Component: AuditReviewScene },
];

export interface SceneManagerProps {
  autoRotateInterval?: number;
  className?: string;
}

export function SceneManager({
  autoRotateInterval = 8000,
  className,
}: SceneManagerProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const shouldReduce = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);

  const sceneCount = SCENE_REGISTRY.length;

  const goNext = useCallback(() => {
    setActiveIndex((prev) => (prev + 1) % sceneCount);
  }, [sceneCount]);

  const goPrev = useCallback(() => {
    setActiveIndex((prev) => (prev - 1 + sceneCount) % sceneCount);
  }, [sceneCount]);

  const goTo = useCallback((index: number) => {
    setActiveIndex(index);
  }, []);

  useEffect(() => {
    if (isPaused) return;
    const timer = setInterval(goNext, autoRotateInterval);
    return () => clearInterval(timer);
  }, [isPaused, goNext, autoRotateInterval]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      }
    }

    const el = containerRef.current;
    if (el) {
      el.addEventListener("keydown", handleKeyDown);
      return () => el.removeEventListener("keydown", handleKeyDown);
    }
  }, [goNext, goPrev]);

  const activeScene = SCENE_REGISTRY[activeIndex];

  return (
    <div
      ref={containerRef}
      className={cn("flex flex-col md:flex-row gap-6", className)}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      tabIndex={0}
      role="region"
      aria-label="Demo scene viewer"
      aria-roledescription="carousel"
    >
      {/* Sidebar */}
      <nav className="flex md:flex-col gap-1 md:w-56 shrink-0" aria-label="Demo scenes">
        {SCENE_REGISTRY.map((scene, i) => (
          <button
            key={scene.id}
            onClick={() => goTo(i)}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
              i === activeIndex
                ? "bg-primary text-primary-foreground font-medium"
                : "hover:bg-muted text-muted-foreground"
            )}
            aria-current={i === activeIndex ? "true" : undefined}
          >
            <span
              className={cn(
                "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                i === activeIndex
                  ? "bg-primary-foreground text-primary"
                  : "bg-muted-foreground/20 text-muted-foreground"
              )}
            >
              {i + 1}
            </span>
            <span className="truncate">{scene.title}</span>
          </button>
        ))}
      </nav>

      {/* Main scene area */}
      <div className="flex-1 min-w-0">
        {/* Scene title and description */}
        <div className="mb-4">
          <h2 className="text-xl font-semibold">{activeScene.title}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {activeScene.description}
          </p>
        </div>

        {/* Scene content */}
        <div className="relative min-h-[280px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeScene.id}
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -30 }}
              transition={{ duration: shouldReduce ? 0 : 0.3 }}
            >
              <activeScene.Component
                isActive={true}
                onComplete={goNext}
              />
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Controls: prev/next + progress dots */}
        <div className="mt-4 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={goPrev}
            aria-label="Previous scene"
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Prev
          </Button>

          <div className="flex gap-1.5" role="tablist" aria-label="Scene indicators">
            {SCENE_REGISTRY.map((scene, i) => (
              <button
                key={scene.id}
                onClick={() => goTo(i)}
                className={cn(
                  "h-2.5 rounded-full transition-all",
                  i === activeIndex
                    ? "w-6 bg-primary"
                    : "w-2.5 bg-muted-foreground/30 hover:bg-muted-foreground/50"
                )}
                role="tab"
                aria-selected={i === activeIndex}
                aria-label={`Scene ${i + 1}: ${scene.title}`}
              />
            ))}
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={goNext}
            aria-label="Next scene"
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>

        {/* Pause indicator */}
        {isPaused && (
          <p className="mt-2 text-xs text-muted-foreground text-center">
            Auto-rotation paused
          </p>
        )}
      </div>
    </div>
  );
}
