import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

export interface DonnaCardProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: "default" | "interactive" | "flat";
    asChild?: boolean;
}

const DonnaCard = forwardRef<HTMLDivElement, DonnaCardProps>(
    ({ className, variant = "default", ...props }, ref) => {
        return (
            <Card
                ref={ref}
                className={cn(
                    // Base styles
                    "bg-card text-card-foreground transition-all duration-300 ease-out border-border/60",

                    // Variants
                    variant === "default" && "shadow-sm hover:shadow-md",
                    variant === "interactive" &&
                    "cursor-pointer shadow-card hover:shadow-card-hover hover:-translate-y-1 hover:scale-[1.02] active:scale-[0.98]",
                    variant === "flat" && "shadow-none border-transparent bg-transparent",

                    className
                )}
                {...props}
            />
        );
    }
);
DonnaCard.displayName = "DonnaCard";

export {
    DonnaCard,
    CardHeader as DonnaCardHeader,
    CardFooter as DonnaCardFooter,
    CardTitle as DonnaCardTitle,
    CardDescription as DonnaCardDescription,
    CardContent as DonnaCardContent,
};
