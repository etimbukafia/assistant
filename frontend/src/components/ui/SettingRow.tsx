import React from 'react';
import { cn } from '@/lib/utils';
import { DonnaText } from './DonnaText';
import { ChevronRight } from 'lucide-react';

export interface SettingRowProps {
    icon?: React.ReactNode;
    iconColor?: string;
    title: string;
    subtitle?: string;
    onClick?: () => void;
    showArrow?: boolean;
    rightElement?: React.ReactNode;
    destructive?: boolean;
    className?: string;
}

export const SettingRow: React.FC<SettingRowProps> = ({
    icon,
    iconColor,
    title,
    subtitle,
    onClick,
    showArrow = true,
    rightElement,
    destructive,
    className,
}) => {
    const Component = onClick ? 'button' : 'div';

    return (
        <Component
            onClick={onClick}
            className={cn(
                "flex items-center gap-4 p-4 w-full text-left transition-colors",
                onClick && "hover:bg-accent/50 active:bg-accent",
                "border-b border-border/40 last:border-0",
                className
            )}
        >
            {icon && (
                <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: iconColor ? `${iconColor}20` : 'var(--accent-precision-20)' }}
                >
                    {React.cloneElement(icon as React.ReactElement, {
                        size: 20,
                        className: cn(iconColor ? `text-[${iconColor}]` : "text-accent-precision")
                    })}
                </div>
            )}
            <div className="flex-1 min-w-0">
                <DonnaText
                    className={cn(
                        "font-medium",
                        destructive ? "text-destructive" : "text-foreground"
                    )}
                >
                    {title}
                </DonnaText>
                {subtitle && (
                    <DonnaText variant="caption" className="text-muted-foreground mt-0.5 block truncate">
                        {subtitle}
                    </DonnaText>
                )}
            </div>
            {rightElement}
            {showArrow && onClick && !rightElement && (
                <ChevronRight size={18} className="text-muted-foreground shrink-0" />
            )}
        </Component>
    );
};
