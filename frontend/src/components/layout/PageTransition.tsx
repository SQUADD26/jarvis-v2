import type { ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";

type PageTransitionProps = {
  children: ReactNode;
  direction?: "forward" | "backward" | "lateral";
  transitionKey?: string;
};

const variants = {
  forward: {
    initial: { opacity: 0, y: 6 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -4 },
  },
  backward: {
    initial: { opacity: 0, y: -4 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 6 },
  },
  lateral: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
};

const transition = {
  duration: 0.3,
  ease: [0.22, 1, 0.36, 1] as const,
};

export default function PageTransition({
  children,
  direction = "forward",
  transitionKey,
}: PageTransitionProps) {
  const variant = variants[direction];

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={transitionKey}
        initial={variant.initial}
        animate={variant.animate}
        exit={variant.exit}
        transition={transition}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
