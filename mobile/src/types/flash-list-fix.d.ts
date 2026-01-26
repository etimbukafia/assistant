import '@shopify/flash-list';

declare module '@shopify/flash-list' {
    export interface FlashListProps<T> {
        /**
         * Estimated average size of items in the list.
         * Providing this prop helps the list render items efficiently.
         */
        estimatedItemSize?: number;
    }
}
