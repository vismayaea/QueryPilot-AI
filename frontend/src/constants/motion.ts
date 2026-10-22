import type { Transition, Variants } from 'motion/react'

// Physics-based spring presets
export const springGentle: Transition = {
  type: 'spring',
  stiffness: 160,
  damping: 24,
  mass: 1,
}

export const springSnappy: Transition = {
  type: 'spring',
  stiffness: 380,
  damping: 28,
  mass: 0.8,
}

export const springBouncy: Transition = {
  type: 'spring',
  stiffness: 420,
  damping: 20,
  mass: 0.9,
}

export const springHero: Transition = {
  type: 'spring',
  stiffness: 90,
  damping: 18,
  mass: 1.2,
}

// Ease curves for smooth non-spring cinematic transitions
export const easeInOutCubic = [0.65, 0, 0.35, 1] as const
export const easeOutExpo = [0.16, 1, 0.3, 1] as const

// Hero entrance orchestrator
export const heroContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.08,
    },
  },
}

export const heroItemVariants: Variants = {
  hidden: { opacity: 0, y: 32, filter: 'blur(8px)' },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: {
      duration: 0.8,
      ease: easeOutExpo,
    },
  },
}

// Staggered list reveals
export const staggerListVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.06,
    },
  },
}

export const listItemVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: easeOutExpo,
    },
  },
}

// Drawer / Slide-over variants
export const drawerVariants: Variants = {
  hidden: { x: '100%', opacity: 0.5 },
  visible: {
    x: 0,
    opacity: 1,
    transition: {
      type: 'spring',
      stiffness: 300,
      damping: 32,
    },
  },
  exit: {
    x: '100%',
    opacity: 0,
    transition: {
      duration: 0.25,
      ease: [0.4, 0, 1, 1],
    },
  },
}

// Modal / Backdrop variants
export const backdropVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.25 } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
}

export const modalVariants: Variants = {
  hidden: { opacity: 0, scale: 0.94, y: 20 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: springSnappy,
  },
  exit: {
    opacity: 0,
    scale: 0.96,
    y: 12,
    transition: { duration: 0.18 },
  },
}

// Card interactive motion
export const cardHoverMotion = {
  whileHover: { y: -4, transition: springSnappy },
  whileTap: { scale: 0.98, transition: { duration: 0.1 } },
}

// Button micro-interaction
export const buttonTapMotion = {
  whileHover: { scale: 1.02 },
  whileTap: { scale: 0.96 },
  transition: { duration: 0.15 },
}
