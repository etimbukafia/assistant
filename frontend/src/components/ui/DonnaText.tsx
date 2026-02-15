import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { VariantProps, cva } from "class-variance-authority";

const textVariants = cva("text-foreground", {
    variants: {
        variant: {
            h1: "font-playfair text-4xl font-bold tracking-tight text-obsidian",
            h2: "font-playfair text-3xl font-semibold tracking-tight text-obsidian",
            h3: "font-playfair text-2xl font-medium tracking-normal text-obsidian",
            h4: "font-playfair text-xl font-medium tracking-normal text-obsidian",
            body: "font-inter text-base font-normal leading-relaxed text-muted-foreground",
            caption: "font-inter text-sm font-medium text-muted-foreground/80",
            label: "font-inter text-xs font-semibold uppercase tracking-wider text-muted-foreground/70",
            error: "font-inter text-sm font-medium text-destructive",
        },
        weight: {
            default: "",
            medium: "font-medium",
            semibold: "font-semibold",
            bold: "font-bold",
        },
        align: {
            left: "text-left",
            center: "text-center",
            right: "text-right",
        },
    },
    defaultVariants: {
        variant: "body",
        align: "left",
    },
});

export interface DonnaTextProps
    extends React.HTMLAttributes<HTMLElement>,
    VariantProps<typeof textVariants> {
    as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p" | "span" | "div" | "label";
}

const DonnaText = forwardRef<HTMLElement, DonnaTextProps>(
    ({ className, variant, weight, align, as, ...props }, ref) => {
        // Auto-map variant to tag if 'as' is not provided
        const Component = as || (variant?.startsWith("h") ? (variant as any) : "p");

        return (
            <Component
                ref={ref as any}
                className={cn(textVariants({ variant, weight, align, className }))}
                {...props}
            />
        );
    }
);
DonnaText.displayName = "DonnaText";

export { DonnaText, textVariants };
